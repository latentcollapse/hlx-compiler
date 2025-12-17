"""
HLX Content-Addressed Shader Database

"GitHub for Shaders" - deterministic, deduplicated, queryable SPIR-V storage.

This is the infrastructure that enables shader reuse, dependency elimination,
and the foundation for the HLX ecosystem.
"""

from typing import Optional, Dict, List, Any, Union
from pathlib import Path
from dataclasses import dataclass
import json
import sqlite3
import hashlib
import datetime


@dataclass
class ShaderMetadata:
    """Searchable metadata attached to a shader."""
    name: str
    shader_stage: str  # "compute" | "vertex" | "fragment"
    entry_point: str
    workgroup_size: Optional[List[int]]  # [x, y, z] for compute
    descriptor_bindings: List[Dict[str, Any]]  # [{binding: 0, type: "StorageBuffer"}]
    source_hash: Optional[str]  # Hash of GLSL source if available
    created_at: str  # ISO 8601 timestamp
    tags: List[str]  # User-defined tags


class ShaderHandle:
    """
    Content-addressed shader handle.

    Format: &h_shader_<blake2b_256_hex>

    The handle is deterministic: same SPIR-V bytes = same handle.
    """
    PREFIX = "&h_shader_"

    def __init__(self, handle: str):
        if not handle.startswith(self.PREFIX):
            raise ValueError(f"Invalid shader handle: {handle}")
        self._handle = handle
        self._hash = handle[len(self.PREFIX):]

    @classmethod
    def from_spirv(cls, spirv_bytes: bytes) -> "ShaderHandle":
        """Create handle from SPIR-V bytes (deterministic)."""
        h = hashlib.blake2b(spirv_bytes, digest_size=32).hexdigest()
        return cls(f"{cls.PREFIX}{h}")

    @property
    def hash(self) -> str:
        """64-char hex hash."""
        return self._hash

    @property
    def prefix(self) -> str:
        """First 2 chars for filesystem lookup."""
        return self._hash[:2]

    @property
    def suffix(self) -> str:
        """Remaining chars for filename."""
        return self._hash[2:]

    def __str__(self) -> str:
        return self._handle

    def __repr__(self) -> str:
        return f"ShaderHandle({self._handle!r})"

    def __eq__(self, other) -> bool:
        if isinstance(other, ShaderHandle):
            return self._handle == other._handle
        return self._handle == other


class ShaderDatabase:
    """
    Content-addressed shader database.

    "GitHub for Shaders" - stores SPIR-V with queryable metadata.

    Usage:
        db = ShaderDatabase("/var/lib/hlx/shaders")

        # Store (deterministic - same bytes = same handle)
        handle = db.add_shader(spirv_bytes, metadata={
            "name": "pbr_compute",
            "workgroup_size": [16, 16, 1],
            "descriptor_bindings": [{"binding": 0, "type": "StorageBuffer"}]
        })

        # Query (KILLER FEATURE - find shaders by properties)
        results = db.query(workgroup_size=[16, 16, 1])

        # Fetch
        spirv = db.get(handle)
    """

    def __init__(self, path: Union[str, Path] = "/var/lib/hlx/shaders"):
        self.root = Path(path)
        self.objects_dir = self.root / "objects"
        self.index_path = self.root / "index.sqlite"

        # Ensure directories exist
        self.objects_dir.mkdir(parents=True, exist_ok=True)

        # Initialize index
        self._init_index()

    def _init_index(self):
        """Initialize SQLite index."""
        self._conn = sqlite3.connect(str(self.index_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS shaders (
                handle TEXT PRIMARY KEY,
                name TEXT,
                shader_stage TEXT,
                entry_point TEXT,
                workgroup_x INTEGER,
                workgroup_y INTEGER,
                workgroup_z INTEGER,
                spirv_size INTEGER,
                source_hash TEXT,
                created_at TEXT,
                metadata_json TEXT
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_stage ON shaders(shader_stage)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_workgroup ON shaders(workgroup_x, workgroup_y, workgroup_z)
        """)
        self._conn.commit()

    def add_shader(
        self,
        spirv_bytes: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        name: str = "unnamed",
        shader_stage: str = "compute",
        entry_point: str = "main",
        workgroup_size: Optional[List[int]] = None,
        descriptor_bindings: Optional[List[Dict]] = None,
        tags: Optional[List[str]] = None
    ) -> ShaderHandle:
        """
        Add SPIR-V shader to database.

        Content-addressed: same bytes = same handle = no duplicate storage.
        """
        # Validate SPIR-V basics
        if len(spirv_bytes) < 20:
            raise ValueError("SPIR-V too small")
        if len(spirv_bytes) % 4 != 0:
            raise ValueError("SPIR-V must be 4-byte aligned")

        # Check magic
        magic = int.from_bytes(spirv_bytes[:4], 'little')
        if magic != 0x07230203:
            raise ValueError(f"Invalid SPIR-V magic: 0x{magic:08x}")

        # Create handle (deterministic)
        handle = ShaderHandle.from_spirv(spirv_bytes)

        # Check if already exists (deduplication)
        obj_path = self.objects_dir / handle.prefix / handle.suffix
        if obj_path.exists():
            # Already stored - verify integrity
            existing = obj_path.read_bytes()
            if existing == spirv_bytes:
                return handle  # Deduplication win!
            else:
                raise ValueError(f"Hash collision detected for {handle}")

        # Write SPIR-V
        obj_path.parent.mkdir(exist_ok=True)
        obj_path.write_bytes(spirv_bytes)

        # Merge metadata
        if metadata:
            name = metadata.get("name", name)
            shader_stage = metadata.get("shader_stage", shader_stage)
            entry_point = metadata.get("entry_point", entry_point)
            workgroup_size = metadata.get("workgroup_size", workgroup_size)
            descriptor_bindings = metadata.get("descriptor_bindings", descriptor_bindings)
            tags = metadata.get("tags", tags)

        # Index metadata
        wg = workgroup_size or [1, 1, 1]
        now = datetime.datetime.utcnow().isoformat()

        self._conn.execute("""
            INSERT OR REPLACE INTO shaders
            (handle, name, shader_stage, entry_point,
             workgroup_x, workgroup_y, workgroup_z,
             spirv_size, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(handle), name, shader_stage, entry_point,
            wg[0], wg[1], wg[2],
            len(spirv_bytes), now,
            json.dumps({
                "descriptor_bindings": descriptor_bindings or [],
                "tags": tags or []
            })
        ))
        self._conn.commit()

        return handle

    def get(self, handle: Union[str, ShaderHandle]) -> bytes:
        """Get SPIR-V bytes by handle."""
        if isinstance(handle, str):
            handle = ShaderHandle(handle)

        obj_path = self.objects_dir / handle.prefix / handle.suffix
        if not obj_path.exists():
            raise KeyError(f"Shader not found: {handle}")

        return obj_path.read_bytes()

    def exists(self, handle: Union[str, ShaderHandle]) -> bool:
        """Check if shader exists in database."""
        if isinstance(handle, str):
            handle = ShaderHandle(handle)
        return (self.objects_dir / handle.prefix / handle.suffix).exists()

    def query(
        self,
        *,
        name: Optional[str] = None,
        shader_stage: Optional[str] = None,
        workgroup_size: Optional[List[int]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query shaders by metadata.

        THE KILLER FEATURE: Find shaders by their properties.
        """
        sql = "SELECT * FROM shaders WHERE 1=1"
        params = []

        if name:
            sql += " AND name LIKE ?"
            params.append(f"%{name}%")

        if shader_stage:
            sql += " AND shader_stage = ?"
            params.append(shader_stage)

        if workgroup_size:
            sql += " AND workgroup_x = ? AND workgroup_y = ? AND workgroup_z = ?"
            params.extend(workgroup_size)

        sql += f" LIMIT {limit}"

        cursor = self._conn.execute(sql, params)
        results = []

        for row in cursor.fetchall():
            meta_json = json.loads(row[10]) if row[10] else {}

            results.append({
                "handle": row[0],
                "name": row[1],
                "shader_stage": row[2],
                "entry_point": row[3],
                "workgroup_size": [row[4], row[5], row[6]],
                "spirv_size": row[7],
                "created_at": row[9],
                "descriptor_bindings": meta_json.get("descriptor_bindings", []),
                "tags": meta_json.get("tags", [])
            })

        return results

    def list_all(self, limit: int = 100) -> List[str]:
        """List all shader handles."""
        cursor = self._conn.execute("SELECT handle FROM shaders LIMIT ?", (limit,))
        return [row[0] for row in cursor.fetchall()]

    def stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        cursor = self._conn.execute("SELECT COUNT(*), SUM(spirv_size) FROM shaders")
        count, total_size = cursor.fetchone()
        return {
            "shader_count": count or 0,
            "total_spirv_bytes": total_size or 0,
            "index_path": str(self.index_path),
            "objects_path": str(self.objects_dir)
        }

    def close(self):
        """Close database connection."""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Global convenience instance
_global_db: Optional[ShaderDatabase] = None

def get_shader_db(path: str = "/var/lib/hlx/shaders") -> ShaderDatabase:
    """Get or create global shader database."""
    global _global_db
    if _global_db is None:
        _global_db = ShaderDatabase(path)
    return _global_db
