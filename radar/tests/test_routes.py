from radar.routes import Router


def test_router_matches_exact_and_params():
    router = Router()
    router.add("GET", "/api/health", "none", "health")
    router.add("PUT", "/api/work/tasks/{task_id}", "user", "update_task")
    router.add("POST", "/api/work/tasks/{task_id}/breakdown", "user", "breakdown")
    health = router.match("GET", "/api/health")
    assert health is not None
    assert health.auth == "none"
    assert health.params == {}
    task = router.match("PUT", "/api/work/tasks/abc123")
    assert task is not None
    assert task.params["task_id"] == "abc123"
    broken = router.match("POST", "/api/work/tasks/abc123/breakdown")
    assert broken is not None
    assert broken.fn == "breakdown"
    assert router.match("GET", "/api/missing") is None
    assert router.match("POST", "/api/health") is None
