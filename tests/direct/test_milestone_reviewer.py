import json

TITLE = "Docs sprint"
CRITERIA = (
    "Deliver a public quickstart that runs end to end on a clean machine, "
    "covers contract deployment, and documents at least two failure modes."
)


def _deploy(direct_deploy):
    return direct_deploy("contracts/milestone_reviewer.py")


def _grant(contract):
    return contract.open_grant(TITLE, CRITERIA)


def test_open_grant_and_read(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice

    grant_id = _grant(contract)
    assert grant_id == 0
    assert contract.total_grants() == 1

    grant = json.loads(contract.get_grant(0))
    assert grant["title"] == TITLE
    assert grant["criteria"] == CRITERIA
    assert grant["milestone_count"] == 0


def test_open_grant_rejects_short_title(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("too short"):
        contract.open_grant("Docs", CRITERIA)


def test_open_grant_rejects_thin_criteria(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("written out in full"):
        contract.open_grant(TITLE, "Write good docs.")


def test_submit_milestone_and_read(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice
    _grant(contract)

    direct_vm.sender = direct_bob
    milestone_id = contract.submit_milestone(
        0, "Quickstart shipped with deploy steps and a troubleshooting section.", "https://example.com/docs"
    )
    assert milestone_id == 0
    assert contract.total_milestones() == 1

    milestone = json.loads(contract.get_milestone(0))
    assert milestone["status"] == "submitted"
    assert milestone["decision"] is None
    assert milestone["grant_id"] == 0

    grant = json.loads(contract.get_grant(0))
    assert grant["milestone_count"] == 1


def test_submit_milestone_unknown_grant_reverts(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("Unknown grant id"):
        contract.submit_milestone(99, "A perfectly reasonable milestone summary.", "https://example.com/docs")


def test_submit_milestone_rejects_bad_url(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice
    _grant(contract)

    with direct_vm.expect_revert("must be an http"):
        contract.submit_milestone(0, "A perfectly reasonable milestone summary.", "ipfs://bafy")


def test_review_pass(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice
    _grant(contract)
    contract.submit_milestone(
        0, "Quickstart shipped with deploy steps and a troubleshooting section.", "https://example.com/docs"
    )

    direct_vm.mock_web(
        r".*example\.com/docs.*",
        {
            "status": 200,
            "body": "<html><body>Quickstart: deploy, run, and the two known failure modes.</body></html>",
        },
    )
    direct_vm.mock_llm(
        r".*impartial grant reviewer.*",
        json.dumps(
            {
                "decision": "pass",
                "score": 88,
                "findings": ["Quickstart covers deployment", "Two failure modes documented"],
                "reasoning": "Every material criterion is backed by the evidence page.",
            }
        ),
    )

    contract.review_milestone(0)

    milestone = json.loads(contract.get_milestone(0))
    assert milestone["status"] == "reviewed"
    assert milestone["decision"] == "pass"
    assert milestone["score"] == 88
    assert milestone["findings"] == ["Quickstart covers deployment", "Two failure modes documented"]


def test_review_partial(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice
    _grant(contract)
    contract.submit_milestone(
        0, "Quickstart shipped with deploy steps and a troubleshooting section.", "https://example.com/docs"
    )

    direct_vm.mock_web(
        r".*example\.com/docs.*",
        {"status": 200, "body": "<html><body>Draft quickstart, deployment steps only.</body></html>"},
    )
    direct_vm.mock_llm(
        r".*impartial grant reviewer.*",
        json.dumps(
            {
                "decision": "partial",
                "score": 52,
                "findings": ["Deployment covered", "Failure modes missing"],
                "reasoning": "Only deployment is evidenced.",
            }
        ),
    )

    contract.review_milestone(0)

    milestone = json.loads(contract.get_milestone(0))
    assert milestone["decision"] == "partial"
    assert milestone["score"] == 52


def test_review_twice_reverts(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice
    _grant(contract)
    contract.submit_milestone(
        0, "Quickstart shipped with deploy steps and a troubleshooting section.", "https://example.com/docs"
    )

    direct_vm.mock_web(
        r".*example\.com/docs.*",
        {"status": 200, "body": "<html><body>Quickstart is published.</body></html>"},
    )
    direct_vm.mock_llm(
        r".*impartial grant reviewer.*",
        json.dumps({"decision": "pass", "score": 90, "findings": [], "reasoning": ""}),
    )

    contract.review_milestone(0)

    with direct_vm.expect_revert("already reviewed"):
        contract.review_milestone(0)


def test_get_unknown_entities_revert(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("Unknown grant id"):
        contract.get_grant(42)

    with direct_vm.expect_revert("Unknown milestone id"):
        contract.get_milestone(42)
