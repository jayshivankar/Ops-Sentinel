"""Temporal workflow runtime for Ops Sentinel."""

import logging
import sys
from datetime import timedelta
from pathlib import Path
from typing import List

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@activity.defn
async def inspect_services_activity(filter_token: str = None) -> str:
    from ops_sentinel.runtime_gateway import OpsRuntimeGateway, RuntimeUnavailableError

    activity.logger.info("Inspecting services with filter token: %s", filter_token)
    try:
        gateway = OpsRuntimeGateway()
        filters = None

        # Treat generic words as "no filter" — show everything
        _no_filter_tokens = {"all", "everything", "any", "services", "containers", "none", ""}

        if filter_token and filter_token.lower() not in _no_filter_tokens:
            normalized = filter_token.lower()
            if normalized in {"running", "stopped", "paused", "exited", "restarting"}:
                filters = {"status": normalized}
            else:
                # Partial name match — Docker supports substring matching
                filters = {"name": filter_token}

        snapshots = gateway.list_services(include_stopped=True, filters=filters)
        if not snapshots:
            label = f" matching '{filter_token}'" if filter_token else ""
            return f"No services found{label}"

        lines = [f"Discovered {len(snapshots)} service(s):", ""]
        for snapshot in snapshots:
            lines.append(snapshot.summary())
            lines.append("")
        return "\n".join(lines).strip()
    except RuntimeUnavailableError as error:
        raise error
    except Exception as error:
        raise ApplicationError(f"service inspection failed: {error}", non_retryable=True)


@activity.defn
async def health_overview_activity(service_name: str = None) -> str:
    from ops_sentinel.runtime_gateway import OpsRuntimeGateway, RuntimeUnavailableError, ServiceMissingError

    activity.logger.info("Generating health overview for %s", service_name or "all running")
    try:
        gateway = OpsRuntimeGateway()
        if service_name:
            return gateway.inspect_health(service_name).summary()

        running = gateway.list_services(include_stopped=False)
        if not running:
            return "No running services found"

        healthy_count = 0
        lines = [f"Health overview for {len(running)} running service(s):", ""]
        for service in running:
            report = gateway.inspect_health(service.name)
            lines.append(report.summary())
            lines.append("")
            if report.healthy:
                healthy_count += 1

        lines.append(f"Summary: {healthy_count}/{len(running)} services healthy")
        return "\n".join(lines)
    except ServiceMissingError as error:
        raise ApplicationError(str(error), non_retryable=True)
    except RuntimeUnavailableError as error:
        raise error
    except Exception as error:
        raise ApplicationError(f"health overview failed: {error}", non_retryable=True)


@activity.defn
async def collect_logs_activity(service_name: str, lines: int = 100) -> str:
    from ops_sentinel.runtime_gateway import OpsRuntimeGateway, RuntimeUnavailableError, ServiceMissingError

    activity.logger.info("Collecting logs for %s with %s lines", service_name, lines)
    try:
        gateway = OpsRuntimeGateway()
        content = gateway.fetch_logs(service_name, lines=lines)
        if not content:
            return f"No log output found for service '{service_name}'"
        return f"Last {lines} lines for '{service_name}':\n{'=' * 64}\n{content}"
    except ServiceMissingError as error:
        raise ApplicationError(str(error), non_retryable=True)
    except RuntimeUnavailableError as error:
        raise error
    except Exception as error:
        raise ApplicationError(f"log collection failed: {error}", non_retryable=True)


@activity.defn
async def recycle_service_activity(service_name: str) -> str:
    from ops_sentinel.runtime_gateway import OpsRuntimeGateway, RuntimeUnavailableError, ServiceMissingError

    activity.logger.info("Recycling service %s", service_name)
    try:
        gateway = OpsRuntimeGateway()
        restarted = gateway.restart_service(service_name)
        if restarted:
            return f"Service '{service_name}' restarted successfully"
        return f"Service '{service_name}' restart was issued but service is not running"
    except ServiceMissingError as error:
        raise ApplicationError(str(error), non_retryable=True)
    except RuntimeUnavailableError as error:
        raise error
    except Exception as error:
        raise ApplicationError(f"service recycle failed: {error}", non_retryable=True)


@activity.defn
async def build_execution_plan_activity(user_request: str) -> str:
    from config import OPENAI_API_KEY, OPENAI_MODEL_ID
    from openai import OpenAI, AuthenticationError, RateLimitError

    activity.logger.info("Generating execution plan for request: %s", user_request)

    if not OPENAI_API_KEY:
        raise ApplicationError(
            "OPENAI_API_KEY is not configured. Set it in .env and restart the worker.",
            non_retryable=True,
        )

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=OPENAI_MODEL_ID,
            messages=[
                {
                    "role": "system",
                    "content": """You are a Docker container operations planner for a tool called Ops Sentinel.

Your ONLY job is to convert a natural language request into a comma-separated execution plan.
Never explain. Never add punctuation. Only output the plan string.

Available actions (exact syntax required):
  inspect              -> list ALL containers (running + stopped)
  inspect:running      -> list only running containers
  inspect:exited       -> list only stopped/exited containers
  inspect:NAME         -> list containers whose name contains NAME
  health               -> health check ALL running containers
  health:NAME          -> health check the specific container named NAME
  logs:NAME            -> last 100 log lines from container NAME
  logs:NAME:N          -> last N log lines from container NAME
  recycle:NAME         -> restart container named NAME
  recycle:NAME,health:NAME -> restart then health-check NAME

Rules:
- For "all", "everything", "any", "all services", "all containers" -> use bare: inspect
- For "running" containers -> use: inspect:running
- For "stopped" or "exited" containers -> use: inspect:exited
- For service names, use the EXACT name from the request (e.g. ops-sentinel-cache, redis, worker)
- For "restart X" always append a health check: recycle:X,health:X
- For "logs" always require a service name
- Multiple actions are comma-separated with NO spaces around commas

Examples:
"show all services"                          -> inspect
"list everything"                            -> inspect
"show all containers"                        -> inspect
"show running services"                      -> inspect:running
"list running containers"                    -> inspect:running
"what services are stopped"                  -> inspect:exited
"is the cache healthy"                       -> health:ops-sentinel-cache
"check health of redis"                      -> health:ops-sentinel-cache
"how is ops-sentinel-api doing"              -> health:ops-sentinel-api
"check all services health"                  -> health
"inspect health for all services"            -> health
"get logs for worker"                        -> logs:ops-sentinel-worker
"fetch last 50 lines from scheduler"         -> logs:ops-sentinel-scheduler:50
"show me 20 lines of logs from mailer"       -> logs:ops-sentinel-mailer:20
"restart the cache"                          -> recycle:ops-sentinel-cache,health:ops-sentinel-cache
"restart gateway and verify it came back"    -> recycle:ops-sentinel-gateway,health:ops-sentinel-gateway
"restart db and check health"                -> recycle:ops-sentinel-db,health:ops-sentinel-db
"show logs for audit service"                -> logs:ops-sentinel-audit
"what are the running data tier services"    -> inspect:running""",
                },
                {"role": "user", "content": user_request},
            ],
            max_tokens=300,
            temperature=0.2,
        )
        plan_text = response.choices[0].message.content.strip()
        if not plan_text or len(plan_text) > 300:
            activity.logger.warning("Planner returned empty/oversized plan; defaulting to inspect")
            return "inspect"
        activity.logger.info("Execution plan: %s", plan_text)
        return plan_text
    except AuthenticationError as error:
        raise ApplicationError(
            f"OpenAI authentication failed — check your OPENAI_API_KEY: {error}",
            non_retryable=True,
        ) from error
    except RateLimitError as error:
        raise ApplicationError(
            f"OpenAI rate limit exceeded — retry later: {error}",
            non_retryable=True,
        ) from error
    except Exception as error:
        # Surface the real error so the user knows what went wrong
        raise ApplicationError(
            f"AI planner failed: {error}",
            non_retryable=True,
        ) from error


OPS_ACTIVITIES = [
    inspect_services_activity,
    health_overview_activity,
    collect_logs_activity,
    recycle_service_activity,
    build_execution_plan_activity,
]


@workflow.defn
class OpsSentinelWorkflow:
    @workflow.run
    async def run(self, user_request: str) -> str:
        workflow.logger.info("Starting Ops Sentinel workflow for request: %s", user_request)

        plan = await workflow.execute_activity(
            build_execution_plan_activity,
            user_request,
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        steps = [segment.strip() for segment in plan.split(",") if segment.strip()]
        if not steps:
            steps = ["inspect"]

        outputs: List[str] = []
        for step in steps:
            try:
                outputs.append(await self._run_step(step))
            except Exception as error:
                workflow.logger.error("Step failed (%s): %s", step, error)
                outputs.append(f"Step '{step}' failed: {error}")

        return "\n\n".join(outputs)

    async def _run_step(self, step: str) -> str:
        tokens = step.split(":")
        action = tokens[0].strip().lower()
        first = tokens[1].strip() if len(tokens) > 1 else None
        second = tokens[2].strip() if len(tokens) > 2 else None

        if action == "inspect":
            return await workflow.execute_activity(
                inspect_services_activity,
                first,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

        if action == "health":
            return await workflow.execute_activity(
                health_overview_activity,
                first,
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

        if action == "logs":
            if not first:
                return "Step 'logs' requires a service name"
            line_count = int(second) if second else 100
            return await workflow.execute_activity(
                collect_logs_activity,
                args=[first, line_count],
                start_to_close_timeout=timedelta(seconds=12),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

        if action == "recycle":
            if not first:
                return "Step 'recycle' requires a service name"
            return await workflow.execute_activity(
                recycle_service_activity,
                first,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=4),
            )

        return f"Unknown action: {action}"
