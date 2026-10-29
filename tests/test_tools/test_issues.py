from unittest.mock import AsyncMock, patch

import pytest

from redmine_mcp.server import mcp


@pytest.mark.asyncio
async def test_tools_registered():
    """Verify that all expected tools are registered."""
    tool_names = set(mcp._tool_manager._tools.keys())
    expected = {
        "list_issues", "get_issue", "search_issues",
        "create_issue", "update_issue", "add_comment",
        "bulk_update_issues",
        "list_issue_relations", "create_issue_relation",
        "update_issue_relation", "delete_issue_relation",
        "list_projects", "get_project",
        "list_statuses", "list_trackers", "list_priorities", "list_users",
        "list_wiki_pages", "get_wiki_page", "get_ticket_rules",
    }
    assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"


@pytest.fixture
def mock_client():
    from redmine_mcp.client import RedmineClient

    with patch.object(RedmineClient, "__init__", lambda self, **kw: None):
        client = RedmineClient()
        client.get = AsyncMock()
        client.post = AsyncMock()
        client.delete = AsyncMock(return_value={})
        return client


def _tool(mock_client, name):
    from mcp.server.fastmcp import FastMCP

    from redmine_mcp.tools import issues

    mcp = FastMCP("test")
    issues.register(mcp, mock_client)
    return mcp._tool_manager._tools[name].fn


@pytest.mark.asyncio
async def test_list_issue_relations(mock_client):
    mock_client.get.return_value = {"relations": [{"id": 1}]}

    result = await _tool(mock_client, "list_issue_relations")(issue_id=10)

    mock_client.get.assert_called_once_with("/issues/10/relations.json")
    assert result["relations"][0]["id"] == 1


@pytest.mark.asyncio
async def test_create_issue_relation(mock_client):
    mock_client.post.return_value = {"relation": {"id": 5}}

    result = await _tool(mock_client, "create_issue_relation")(
        issue_id=10, issue_to_id=20, relation_type="precedes", delay=2
    )

    mock_client.post.assert_called_once_with(
        "/issues/10/relations.json",
        json={"relation": {"issue_to_id": 20, "relation_type": "precedes", "delay": 2}},
    )
    assert result["relation"]["id"] == 5


@pytest.mark.asyncio
async def test_create_issue_relation_default_type(mock_client):
    await _tool(mock_client, "create_issue_relation")(issue_id=10, issue_to_id=20)

    mock_client.post.assert_called_once_with(
        "/issues/10/relations.json",
        json={"relation": {"issue_to_id": 20, "relation_type": "relates"}},
    )


@pytest.mark.asyncio
async def test_update_issue_relation(mock_client):
    mock_client.get.return_value = {
        "relation": {"id": 5, "issue_id": 10, "issue_to_id": 20,
                     "relation_type": "relates", "delay": None}
    }
    mock_client.post.return_value = {"relation": {"id": 6}}

    result = await _tool(mock_client, "update_issue_relation")(
        relation_id=5, relation_type="blocks"
    )

    mock_client.get.assert_called_once_with("/relations/5.json")
    mock_client.delete.assert_called_once_with("/relations/5.json")
    mock_client.post.assert_called_once_with(
        "/issues/10/relations.json",
        json={"relation": {"issue_to_id": 20, "relation_type": "blocks"}},
    )
    assert result["relation"]["id"] == 6


@pytest.mark.asyncio
async def test_update_issue_relation_restores_on_failure(mock_client):
    mock_client.get.return_value = {
        "relation": {"id": 5, "issue_id": 10, "issue_to_id": 20,
                     "relation_type": "precedes", "delay": 3}
    }
    mock_client.post.side_effect = [RuntimeError("422"), {"relation": {"id": 7}}]

    with pytest.raises(RuntimeError):
        await _tool(mock_client, "update_issue_relation")(relation_id=5, issue_to_id=99)

    assert mock_client.post.call_count == 2
    assert mock_client.post.call_args_list[1].kwargs["json"] == {
        "relation": {"issue_to_id": 20, "relation_type": "precedes", "delay": 3}
    }


@pytest.mark.asyncio
async def test_delete_issue_relation(mock_client):
    await _tool(mock_client, "delete_issue_relation")(relation_id=5)

    mock_client.delete.assert_called_once_with("/relations/5.json")
