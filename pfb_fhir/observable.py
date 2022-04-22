"""Class hierarchy of Model."""

import uuid
from typing import Any, Callable

from pydantic import BaseModel
from pydantic_yaml import YamlModelMixin
import abc
import logging

from pfb_fhir.common import first_occurrence

logger = logging.getLogger(__name__)


class ObservableData(BaseModel):
    """Any data item has an envelope of source and destination with a payload."""

    id: str
    """Envelope."""
    payload: Any
    """The source data."""
    observers: list[Callable]
    """A list of handlers."""
    # TODO What we really want here is a list of Observer,
    #   but that creates a circular reference, perhaps a python 'interface'?

    def __init__(self,  payload: dict, _id: str = None, source: dict = None, destination: dict = None,
                 observers: list = None, **data) -> None:
        """Init data with pydantic, observers locally."""
        if not observers:
            observers = []
        if not _id:
            _id = str(uuid.uuid4())
        if not destination:
            destination = {}
        if not source:
            source = {}

        super().__init__(id=_id, source=source, destination=destination, payload=payload, observers=observers, **data)

    def register_observer(self, observer):
        """Add observer to our list."""
        self.observers.append(observer)

    def notify_observers(self, *args, **kwargs):
        """Tell observers to process us."""
        for observer in self.observers:
            observer.notify(self, *args, **kwargs)

    def assert_observers(self):
        """Tell observers to process us, chainable."""
        if len(self.observers) == 0:
            if first_occurrence(f"{self.payload['resourceType']} missing observers"):
                logger.warning(f"{self.payload['resourceType']} missing observers")
        # assert len(self.observers) > 0, f"{self.id} {self.payload} missing observers"
        return self


# class ContextConfig:
#     """Allow arbitrary user types for fields."""
#
#     # https://pydantic-docs.helpmanual.io/usage/model_config/
#     arbitrary_types_allowed = True


# @dataclass(config=ContextConfig)
class Context(BaseModel):
    """Transient data for command(s)."""

    obj: dict = {}


class Observer(YamlModelMixin, BaseModel, abc.ABC):
    """Event sink."""

    id: str
    """Synonymous with Profile.id"""

    def __init__(self, observable: ObservableData = None,  _id: str = None, **data) -> None:
        """Init id with pydantic, dispatch registration."""
        # handle serializer input
        if 'id' in data:
            assert _id is None
            _id = data['id']
            del data['id']

        # default to class name
        if not _id:
            _id = type(self).__name__

        super().__init__(id=_id, **data)

        if observable and not isinstance(observable, (ObservableData, list, )):
            raise TypeError(f"{type(observable)} is not Observable, please wrap in ObservableData.")
        if observable:
            self.observe(observable)

    def observe(self, observable: ObservableData) -> ObservableData:
        """Register self with data if interested."""
        if observable:
            if not isinstance(observable, list):
                observable = [observable]
            [_observable.register_observer(self) for _observable in observable if self.interested(_observable)]
        return observable

    @abc.abstractmethod
    def interested(self, observable: ObservableData) -> bool:
        """Get notified? Please override this method."""
        pass

    @abc.abstractmethod
    def notify(self, observable: ObservableData, context: Context = None, *args, **kwargs) -> None:
        """Process data. Please override this method."""
        pass


class Command(Observer, abc.ABC):
    """Process a data item with a context."""

    pass
