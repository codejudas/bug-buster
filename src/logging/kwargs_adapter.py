import logging
from datetime import datetime
from typing import MutableMapping, Any, Tuple
from uuid import UUID

from pydantic import BaseModel


class KwargsContextLoggerAdapter(logging.LoggerAdapter):
    """
    A wrapper so that we can pass additional context via arbitrary kwarg params on logging functions. ie:
    log.info('hello', user_id=user_id)
    ...
    """

    # Named params on logging.info etc... that we want to preserve
    METHOD_PARAMS = {"exc_info", "extra", "stack_info", "stacklevel"}

    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> Tuple[Any, MutableMapping[str, Any]]:
        """
        Support passing arbitrary kwargs to a logger and for them to be stored in metadata variable on LogRecord
        Note(evan): The reason that we put this under a nested 'metadata' key in 'extra' is because when the log gets
                    converted to a LogRecord by the python lib it just squashes every key in extra as an attribute
                    on LogRecord, which makes it a bit difficult for us to tell what came from our code vs provided
                    by the library (like logger name, line no, etc..)
        """
        metadata = {}
        for k in list(kwargs.keys()):
            if k not in self.METHOD_PARAMS:
                v = kwargs.pop(k)
                metadata[k] = self._serialize_objects(v)
            elif k == "extra":
                # Flatten into extra
                v_dict = kwargs.pop(k)
                v_dict = {kk: self._serialize_objects(v) for kk, v in v_dict.items()}
                metadata.update(v_dict)

        # Also store in json_fields as that's what GCP logger expects
        kwargs["extra"] = {"metadata": metadata, "json_fields": metadata}
        return msg, kwargs

    @classmethod
    def _serialize_objects(cls, obj: Any) -> Any:
        """
        Logging adapter supports passing any object as a kwarg for debugging, but downstream handlers (logtail)
        cannot serialize some of them, we can add exceptions here to suppress errors on a case by case basis.
        """
        if isinstance(obj, UUID):
            return str(obj)

        if isinstance(obj, datetime):
            return str(obj)

        if isinstance(obj, BaseModel):
            return {k: cls._serialize_objects(v) for k, v in obj.model_dump().items()}

        return obj