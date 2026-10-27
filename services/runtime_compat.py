"""One-time recovery for running previews with classes from the prior app revision.

Session state is untouched. app.boot rehydrates the retained JSON into current models.
Fresh processes and current imports require no action.
"""

import sys


def recover_stale_imports(modules):
    models = modules.get("services.models")
    old_models = models is not None and "decision_bases" not in getattr(
        getattr(models, "Plan", None), "model_fields", {}
    )
    ui = modules.get("ui_drafts")
    code = getattr(getattr(ui, "capture", None), "__code__", None)
    old_helper = code is not None and code.co_argcount != 2
    future = modules.get("future_inputs")
    old_future = future is not None and (
        not hasattr(future, "future_screen") or getattr(future, "GROUPED_UI_VERSION", None) != 12
    )
    review = modules.get("review_inputs")
    old_review = review is not None and getattr(review, "FINAL_REVIEW_UI_VERSION", None) != 14
    pricing = modules.get("pricing_inputs")
    old_pricing = pricing is not None and getattr(pricing, "PRICING_UI_VERSION", None) != 3
    proposal = modules.get("proposal_inputs")
    old_proposal = proposal is not None and getattr(proposal, "PROPOSAL_UI_VERSION", None) != 2
    evidence = modules.get("services.evidence")
    old_quotes = evidence is not None and getattr(evidence, "PRIVATE_PROPOSAL_QUOTES_VERSION", None) != 1
    agent = modules.get("services.agent")
    old_agent = agent is not None and getattr(agent, "PROPOSAL_REVIEW_VERSION", None) != 1
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
            "decision_inputs",
            "future_inputs",
            "ui_drafts",
            "hybrid_inputs",
            "journey_inputs",
            "pricing_inputs",
            "review_inputs",
            "proposal_inputs",
        }
        for name in list(modules):
            if (
                name in helpers
                or (old_proposal and name in {"services.proposals", "services.proposal_export"})
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
