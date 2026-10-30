"""Unit tests for Unified Memory Hub."""

from pathlib import Path
from pab.core.config import ConfigManager
from pab.core.models.memory import MemoryItem
from pab.memory.dedup import compute_memory_hash, find_duplicates
from pab.memory.hub import MemoryHub


def test_memory_add_and_deduplication(config_mgr: ConfigManager):
    hub = MemoryHub(config_mgr)

    item1 = MemoryItem(
        id="mem-1",
        title="PostgreSQL Failover Setup",
        content="Use Patroni with etcd for high-availability leader elections.",
        scope="project",
    )
    hub.add_memory(item1)

    # Identical content with differing whitespace/case
    item2 = MemoryItem(
        id="mem-2",
        title="PostgreSQL Failover Guide",
        content="Use patroni with etcd for high-availability leader elections.  ",
        scope="project",
    )

    dups = find_duplicates([item1, item2])
    assert len(dups) == 1
    assert len(dups[0]) == 2


def test_memory_search(config_mgr: ConfigManager):
    hub = MemoryHub(config_mgr)

    hub.add_memory(
        MemoryItem(
            id="mem-k8s",
            title="Kubernetes CNI Policy",
            content="Use Cilium eBPF for cluster network policy enforcement.",
            scope="global",
            tags=["networking", "cilium"],
        )
    )
    hub.add_memory(
        MemoryItem(
            id="mem-db",
            title="Database Connection Pooler",
            content="PgBouncer configured with transaction pooling mode.",
            scope="project",
            tags=["postgres", "pgbouncer"],
        )
    )

    results = hub.search("Cilium")
    assert len(results) == 1
    assert results[0].id == "mem-k8s"

    results_db = hub.search("transaction pooling")
    assert len(results_db) == 1
    assert results_db[0].id == "mem-db"


def test_memory_backup(config_mgr: ConfigManager):
    hub = MemoryHub(config_mgr)
    hub.add_memory(
        MemoryItem(
            id="mem-test",
            title="Test Memory",
            content="Temporary memory for snapshot test.",
            scope="global",
        )
    )

    backup_path = hub.backup_memories()
    assert backup_path.is_dir()
    assert (backup_path / "global" / "mem-test.md").is_file()
