from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
from solders.pubkey import Pubkey
from anchorpy.borsh_extension import BorshPubkey
import borsh_construct as borsh


class InitEndpointParamsJSON(typing.TypedDict):
    eid: int
    admin: str


@dataclass
class InitEndpointParams:
    layout: typing.ClassVar = borsh.CStruct("eid" / borsh.U32, "admin" / BorshPubkey)
    eid: int
    admin: Pubkey

    @classmethod
    def from_decoded(cls, obj: Container) -> "InitEndpointParams":
        return cls(eid=obj.eid, admin=obj.admin)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"eid": self.eid, "admin": self.admin}

    def to_json(self) -> InitEndpointParamsJSON:
        return {"eid": self.eid, "admin": str(self.admin)}

    @classmethod
    def from_json(cls, obj: InitEndpointParamsJSON) -> "InitEndpointParams":
        return cls(eid=obj["eid"], admin=Pubkey.from_string(obj["admin"]))
