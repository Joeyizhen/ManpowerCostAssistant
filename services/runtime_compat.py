"""One-time recovery for running previews with classes from the prior app revision.

Session state is untouched. app.boot rehydrates the retained JSON into current models.
Fresh processes and current imports require no action.
"""

import sys


def recover_stale_imports(modules):
    demo = modules.get("services.demo")
    if demo is not None and getattr(demo, "DEMO_VERSION", None) != 2:
        # Refresh only future example loads; never replace the officer's active plan.
        modules.pop("services.demo")
    models = modules.get("services.models")
    old_models = models is not None and "decision_bases" not in getattr(
        getattr(models, "Plan", None), "model_fields", {}
    )
    old_models = old_models or (
        models is not None
        and hasattr(models, "Role")
        and getattr(models, "REFERENCE_MODEL_VERSION", None) != 1
    )
    reference = modules.get("services.reference_data")
    routing = modules.get("services.cost_routing")
    old_models = old_models or (routing is not None and getattr(routing, "ROUTING_VERSION", None) != 2)
    old_models = old_models or (
        reference is not None and getattr(reference, "REFERENCE_SERVICE_VERSION", None) != 3
    )
    old_models = old_models or (
        models is not None and hasattr(models, "Role") and getattr(models, "OFFICER_UX_VERSION", None) != 11
    )
    workflow = modules.get("services.workflow")
    old_models = old_models or (workflow is not None and getattr(workflow, "WORKFLOW_VERSION", None) != 2)
    ui = modules.get("ui_drafts")
    code = getattr(getattr(ui, "capture", None), "__code__", None)
    old_helper = code is not None and code.co_argcount != 2
    journey = modules.get("journey_inputs")
    old_helper = old_helper or (journey is not None and getattr(journey, "HEADCOUNT_UI_VERSION", None) != 2)
    navigation = modules.get("activity_nav")
    old_helper = old_helper or (
        navigation is not None and getattr(navigation, "NAVIGATION_UI_VERSION", None) != 1
    )
    deployment = modules.get("hybrid_inputs")
    old_helper = old_helper or (
        deployment is not None and getattr(deployment, "DEPLOYMENT_REVIEW_UI_VERSION", None) != 3
    )
    future = modules.get("future_inputs")
    old_future = future is not None and (
        not hasattr(future, "future_screen") or getattr(future, "GROUPED_UI_VERSION", None) != 18
    )
    review = modules.get("review_inputs")
    old_review = review is not None and getattr(review, "FINAL_REVIEW_UI_VERSION", None) != 20
    pricing = modules.get("pricing_inputs")
    old_pricing = pricing is not None and getattr(pricing, "PRICING_UI_VERSION", None) != 8
    proposal = modules.get("proposal_inputs")
    old_proposal = proposal is not None and getattr(proposal, "PROPOSAL_UI_VERSION", None) != 6
    evidence = modules.get("services.evidence")
    old_quotes = evidence is not None and getattr(evidence, "PRIVATE_PROPOSAL_QUOTES_VERSION", None) != 1
    agent = modules.get("services.agent")
    old_agent = agent is not None and getattr(agent, "PROPOSAL_REVIEW_VERSION", None) != 3
    if (
        old_models
        or old_helper
        or old_future
        or old_review
        or old_pricing
        or old_proposal
        or old_quotes
        or old_agent
    ):
        helpers = {
            "activity_nav",
            "decision_inputs",
            "future_inputs",
            "ui_drafts",
            "hybrid_inputs",
            "journey_inputs",
            "pricing_inputs",
            "selection_controls",
            "review_inputs",
            "proposal_inputs",
            "proposal_journey",
        }
        for name in list(modules):
            if (
                name in helpers
                or (old_models and name in {"agent2_views", "agent2_track4_views"})
                or (
                    old_proposal
                    and name in {"services.proposals", "services.proposal_export", "services.proposal_intake"}
                )
                or (old_agent and name == "services.agent")
                or (
                    old_quotes
                    and name
                    in {
                        "services.evidence",
                        "services.calculations",
                        "services.workflow",
                        "services.agent",
                        "services.decision_basis",
                        "services.hybrid",
                        "services.final_review",
                        "services.pricing",
                        "services.future_groups",
                        "services.proposals",
                        "services.proposal_export",
                        "services.journey",
                        "services.export",
                    }
                )
                or (old_pricing and name == "services.pricing")
                or (old_review and name in {"services.final_review", "services.hybrid"})
                or (
                    old_future
                    and name
                    in {
                        "services.decision_basis",
                        "services.export",
                        "services.pricing",
                        "services.future_groups",
                    }
                )
                or (old_models and name.startswith("services.") and name != __name__)
            ):
                modules.pop(name)
    return (
        old_models
        or old_helper
        or old_future
        or old_review
        or old_pricing
        or old_proposal
        or old_quotes
        or old_agent
    )


RECOVERED = recover_stale_imports(sys.modules)
