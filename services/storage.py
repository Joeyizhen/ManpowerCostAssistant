"""Owned durable snapshots, atomic optimistic updates, preserved uploads within the snapshot."""

from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, delete, select, update
from sqlalchemy.exc import IntegrityError

from services.models import Plan, now


class ConflictError(ValueError):
    pass


class Store:
    def __init__(self, url):
        if url.startswith("sqlite:///") and ":memory:" not in url:
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, pool_pre_ping=True)
        meta = MetaData()
        self.projects = Table(
            "projects",
            meta,
            Column("id", String(80), primary_key=True),
            Column("owner", String(128), nullable=False, index=True),
            Column("name", String(300)),
            Column("revision", Integer, nullable=False),
            Column("updated", String(80)),
            Column("body", Text, nullable=False),
        )
        self.snapshots = Table(
            "snapshots",
            meta,
            Column("id", String(80), primary_key=True),
            Column("revision", Integer, primary_key=True),
            Column("owner", String(128), nullable=False),
            Column("body", Text, nullable=False),
        )
        meta.create_all(self.engine)

    def list(self, owner):
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(
                        self.projects.c.id,
                        self.projects.c.name,
                        self.projects.c.updated,
                        self.projects.c.revision,
                    )
                    .where(self.projects.c.owner == owner)
                    .order_by(self.projects.c.updated.desc())
                )
                .mappings()
                .all()
            )
            return [dict(r) for r in rows]

    def load(self, project_id, owner):
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(self.projects).where(
                        self.projects.c.id == project_id, self.projects.c.owner == owner
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ValueError("Project not found or access denied")
            return Plan.model_validate_json(row["body"]), row["revision"]

    def save(self, plan, owner, expected_revision):
        from services.journey import working_draft

        name = working_draft(plan).profile.name
        body = plan.model_dump_json()
        revision = expected_revision + 1
        try:
            with self.engine.begin() as conn:
                if expected_revision == 0:
                    conn.execute(
                        self.projects.insert().values(
                            id=plan.id,
                            owner=owner,
                            name=name,
                            revision=revision,
                            updated=now(),
                            body=body,
                        )
                    )
                else:
                    updated = conn.execute(
                        update(self.projects)
                        .where(
                            self.projects.c.id == plan.id,
                            self.projects.c.owner == owner,
                            self.projects.c.revision == expected_revision,
                        )
                        .values(name=name, revision=revision, updated=now(), body=body)
                    )
                    if updated.rowcount != 1:
                        raise ConflictError(
                            "A newer saved revision exists. Save a local snapshot, then reload before editing."
                        )
                conn.execute(
                    self.snapshots.insert().values(id=plan.id, owner=owner, revision=revision, body=body)
                )
        except IntegrityError:
            raise ConflictError("Project already exists; reload its newest revision") from None
        return revision

    def delete(self, project_id, owner, expected_revision):
        """Delete only the owned revision the officer explicitly selected, including its history."""
        if expected_revision < 1:
            raise ValueError("Select a saved project before deleting")
        with self.engine.begin() as conn:
            removed = conn.execute(
                delete(self.projects).where(
                    self.projects.c.id == project_id,
                    self.projects.c.owner == owner,
                    self.projects.c.revision == expected_revision,
                )
            )
            if removed.rowcount != 1:
                raise ConflictError(
                    "The project changed or is no longer available. Select it again before deleting."
                )
            conn.execute(
                delete(self.snapshots).where(
                    self.snapshots.c.id == project_id, self.snapshots.c.owner == owner
                )
            )
