from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class InitConfigArgs(typing.TypedDict):
    params: types.init_config_params.InitConfigParams


layout = borsh.CStruct("params" / types.init_config_params.InitConfigParams.layout)


class InitConfigAccounts(typing.TypedDict):
    delegate: Pubkey
    oapp_registry: Pubkey
    message_lib_info: Pubkey
    message_lib: Pubkey
    message_lib_program: Pubkey


def init_config(
    args: InitConfigArgs,
    accounts: InitConfigAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["delegate"], is_signer=True, is_writable=False),
        AccountMeta(
            pubkey=accounts["oapp_registry"], is_signer=False, is_writable=False
        ),
        AccountMeta(
            pubkey=accounts["message_lib_info"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=accounts["message_lib"], is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=accounts["message_lib_program"], is_signer=False, is_writable=False
        ),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\x17\xebs\xe8\xa8`\x01\xe7"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
