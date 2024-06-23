import typing
from dataclasses import dataclass
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
import borsh_construct as borsh
from anchorpy.coder.accounts import ACCOUNT_DISCRIMINATOR_SIZE
from anchorpy.error import AccountInvalidDiscriminator
from anchorpy.utils.rpc import get_multiple_accounts
from anchorpy.borsh_extension import BorshPubkey
from ..program_id import PROGRAM_ID


class UserJSON(typing.TypedDict):
    authority: str
    user_bump: int
    match_count: int


@dataclass
class User:
    discriminator: typing.ClassVar = b"\x9fu_\xe3\xef\x97:\xec"
    layout: typing.ClassVar = borsh.CStruct(
        "authority" / BorshPubkey, "user_bump" / borsh.U8, "match_count" / borsh.U8
    )
    authority: Pubkey
    user_bump: int
    match_count: int

    @classmethod
    async def fetch(
        cls,
        conn: AsyncClient,
        address: Pubkey,
        commitment: typing.Optional[Commitment] = None,
        program_id: Pubkey = PROGRAM_ID,
    ) -> typing.Optional["User"]:
        resp = await conn.get_account_info(address, commitment=commitment)
        info = resp.value
        if info is None:
            return None
        if info.owner != program_id:
            raise ValueError("Account does not belong to this program")
        bytes_data = info.data
        return cls.decode(bytes_data)

    @classmethod
    async def fetch_multiple(
        cls,
        conn: AsyncClient,
        addresses: list[Pubkey],
        commitment: typing.Optional[Commitment] = None,
        program_id: Pubkey = PROGRAM_ID,
    ) -> typing.List[typing.Optional["User"]]:
        infos = await get_multiple_accounts(conn, addresses, commitment=commitment)
        res: typing.List[typing.Optional["User"]] = []
        for info in infos:
            if info is None:
                res.append(None)
                continue
            if info.account.owner != program_id:
                raise ValueError("Account does not belong to this program")
            res.append(cls.decode(info.account.data))
        return res

    @classmethod
    def decode(cls, data: bytes) -> "User":
        if data[:ACCOUNT_DISCRIMINATOR_SIZE] != cls.discriminator:
            raise AccountInvalidDiscriminator(
                "The discriminator for this account is invalid"
            )
        dec = User.layout.parse(data[ACCOUNT_DISCRIMINATOR_SIZE:])
        return cls(
            authority=dec.authority,
            user_bump=dec.user_bump,
            match_count=dec.match_count,
        )

    def to_json(self) -> UserJSON:
        return {
            "authority": str(self.authority),
            "user_bump": self.user_bump,
            "match_count": self.match_count,
        }

    @classmethod
    def from_json(cls, obj: UserJSON) -> "User":
        return cls(
            authority=Pubkey.from_string(obj["authority"]),
            user_bump=obj["user_bump"],
            match_count=obj["match_count"],
        )
