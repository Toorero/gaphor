import pytest

from gaphor.application import Application
from gaphor.core.eventmanager import event_handler
from gaphor.core.modeling import Diagram
from gaphor.core.modeling.event import AssociationDeleted, ElementDeleted
from gaphor.diagram.presentation import connect
from gaphor.transaction import Transaction
from gaphor.UML.classes import AssociationItem, ClassItem


@pytest.fixture
def application():
    app = Application()
    yield app
    app.shutdown()


@pytest.fixture
def session(application):
    return application.new_session()


@pytest.fixture
def event_manager(session):
    return session.get_service("event_manager")


@pytest.fixture
def element_factory(session):
    return session.get_service("element_factory")


@pytest.fixture
def undo_manager(session):
    return session.get_service("undo_manager")


@pytest.fixture
def diagram(element_factory, event_manager):
    with Transaction(event_manager):
        return element_factory.create(Diagram)


def test_removal_by_unlink(diagram, element_factory, event_manager):
    with Transaction(event_manager):
        asc = diagram.create(AssociationItem)
        c1 = diagram.create(ClassItem)

    with Transaction(event_manager):
        connect(asc, asc.head, c1)

    with Transaction(event_manager):
        asc.unlink()

    assert asc not in element_factory.select()


def test_removal_by_diagram_remove(
    diagram, element_factory, event_manager, undo_manager
):
    with Transaction(event_manager):
        asc = diagram.create(AssociationItem)
        c1 = diagram.create(ClassItem)

    with Transaction(event_manager):
        connect(asc, asc.head, c1)

    with Transaction(event_manager):
        diagram.unlink()

    undo_manager.undo_transaction()

    assert element_factory.lookup(diagram.id)
    assert element_factory.lookup(asc.id)

    undo_manager.redo_transaction()

    assert not element_factory.lookup(diagram.id)
    assert not element_factory.lookup(asc.id)


def test_exception_during_removal_by_diagram_remove(
    diagram, element_factory, event_manager, undo_manager
):

    with Transaction(event_manager):
        cls = diagram.create(ClassItem)

    @event_handler(AssociationDeleted)
    def handler(event):
        if event.element is diagram and event.property is Diagram.ownedPresentation:
            raise Exception()

    event_manager.subscribe(handler)

    with pytest.raises(Exception):
        with Transaction(event_manager):
            cls.unlink()

    assert diagram in element_factory.select()
    assert cls in element_factory.select()
    assert cls.diagram is diagram


@pytest.mark.xfail(
    reason="This test is flaky: depends on event handler execution order"
)
def test_exception_during_unlink_event_handling(
    diagram, element_factory, event_manager
):

    with Transaction(event_manager):
        cls = diagram.create(ClassItem)

    @event_handler(ElementDeleted)
    def handler(event):
        raise Exception()

    event_manager.subscribe(handler)

    with pytest.raises(Exception):
        with Transaction(event_manager):
            cls.unlink()

    undone_cls = element_factory.lookup(cls.id)
    assert diagram in element_factory.select()
    assert undone_cls
    assert undone_cls is not cls
    assert undone_cls.diagram is diagram
    assert undone_cls in diagram.ownedPresentation
    assert cls.diagram is None
