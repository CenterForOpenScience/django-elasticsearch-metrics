import dataclasses


@dataclasses.dataclass
class DjelmeIndexStatus:
    index_name: str
    is_expired: bool = False
