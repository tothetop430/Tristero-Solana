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


class SendLibraryConfigJSON(typing.TypedDict):
    message_lib: str
    bump: int


@dataclass
class SendLibraryConfig:
    discriminator: typing.ClassVar = b"=\xee\x1fH\xfbuB\xb0"
    layout: typing.ClassVar = borsh.CStruct(
        "message_lib" / BorshPubkey, "bump" / borsh.U8
    )
    message_lib: Pubkey
    bump: int

    @classmethod
    async def fetch(
        cls,
        conn: AsyncClient,
        address: Pubkey,
        commitment: typing.Optional[Commitment] = None,
        program_id: Pubkey = PROGRAM_ID,
    ) -> typing.Optional["SendLibraryConfig"]:
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
    ) -> typing.List[typing.Optional["SendLibraryConfig"]]:
        infos = await get_multiple_accounts(conn, addresses, commitment=commitment)
        res: typing.List[typing.Optional["SendLibraryConfig"]] = []
        for info in infos:
            if info is None:
                res.append(None)
                continue
            if info.account.owner != program_id:
                raise ValueError("Account does not belong to this program")
            res.append(cls.decode(info.account.data))
        return res

    @classmethod
    def decode(cls, data: bytes) -> "SendLibraryConfig":
        if data[:ACCOUNT_DISCRIMINATOR_SIZE] != cls.discriminator:
            raise AccountInvalidDiscriminator(
                "The discriminator for this account is invalid"
            )
        dec = SendLibraryConfig.layout.parse(data[ACCOUNT_DISCRIMINATOR_SIZE:])
        return cls(
            message_lib=dec.message_lib,
            bump=dec.bump,
        )

    def to_json(self) -> SendLibraryConfigJSON:
        return {
            "message_lib": str(self.message_lib),
            "bump": self.bump,
        }

    @classmethod
    def from_json(cls, obj: SendLibraryConfigJSON) -> "SendLibraryConfig":
        return cls(
            message_lib=Pubkey.from_string(obj["message_lib"]),
            bump=obj["bump"],
        )
