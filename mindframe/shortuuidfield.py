import sys

import shortuuid
import six
from shortuuidfield import ShortUUIDField


class MFShortUUIDField(ShortUUIDField):
    """
    Allow for col width > 22 because we use a restricted alphabet for readability
    """

    def __init__(self, auto=True, *args, **kwargs):
        self.auto = auto
        # default is to store UUIDs in base57 format, which is fixed at 22 characters
        kwargs["max_length"] = kwargs.get("max_length", 22)
        if auto:
            kwargs["editable"] = False
            kwargs["blank"] = True
        super(ShortUUIDField, self).__init__(*args, **kwargs)
