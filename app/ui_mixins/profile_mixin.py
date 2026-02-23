from .profile_content_mixin import UIProfileContentMixin
from .profile_crud_mixin import UIProfileCrudMixin


class UIProfileMixin(UIProfileCrudMixin, UIProfileContentMixin):
    """Композиция профильных mixin-блоков."""

    pass
