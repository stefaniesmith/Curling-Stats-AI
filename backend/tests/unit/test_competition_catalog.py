from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from curlchat.db.models import Event
from curlchat.db.session import Base
from curlchat.repositories.events import EventRepository
from curlchat.services.competition_catalog import CompetitionCatalog


def test_renders_imported_competition_metadata_without_internal_ids() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all(
        [
            Event(
                display_name="Hearts",
                source_slug="hearts",
                first_event_year=1982,
                last_event_year=2025,
                has_shot_statistics=True,
            ),
            Event(
                display_name="Brier",
                source_slug="brier",
                first_event_year=1927,
                last_event_year=2025,
                has_shot_statistics=False,
            ),
        ]
    )
    session.commit()

    with session:
        table = CompetitionCatalog(EventRepository(session)).render_prompt_table()

    assert "| Competition | Years covered | Shot statistics | Common aliases |" in table
    assert "| Brier | 1927–2025 | Not available | — |" in table
    assert "| Hearts | 1982–2025 | Available | Scotties; Tournament of Hearts |" in table
    assert "event_id" not in table


def test_reports_an_empty_imported_catalog() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        table = CompetitionCatalog(EventRepository(session)).render_prompt_table()

    assert table == "No competitions have been imported yet."
