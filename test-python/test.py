import asyncio
import binascii
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.account import Account
from solders.bankrun import ProgramTestContext
from solders.message import Message
from solders.token.associated import get_associated_token_address
from solders.bankrun import start_anchor
from solders.transaction import TransactionError, VersionedTransaction
from anchorpy import Provider, Program, WorkspaceType, workspace, Idl, Context, create_workspace, close_workspace, Wallet
from solders.system_program import ID as SYS_PROGRAM_ID
from pathlib import Path
from solana.rpc.async_api import AsyncClient
from solana.rpc.api import Client
from solana.transaction import Transaction
from solders.instruction import Instruction, AccountMeta
from solders.message import Message
from solders.compute_budget import set_compute_unit_limit
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed
from anchorpy.borsh_extension import BorshPubkey
import borsh_construct as borsh
import typing

from tristero.instructions.create_match import create_match, CreateMatchAccounts
from tristero.instructions.place_order import place_order, PlaceOrderAccounts
from tristero.instructions.challenge import challenge, ChallengeAccounts
from tristero.instructions.register_tristero_oapp import register_tristero_oapp, RegisterTristeroOappAccounts
from tristero.instructions.lz_receive_types import lz_receive_types, LzReceiveTypesAccounts
from tristero.instructions.send_stored import send_stored, SendStoredAccounts
from endpoint.instructions.init_nonce import init_nonce, InitNonceAccounts
from endpoint.instructions.init_send_library import init_send_library, InitSendLibraryAccounts
from endpoint.instructions.init_receive_library import init_receive_library, InitReceiveLibraryAccounts

from tristero.instructions.register_config import register_config, RegisterConfigAccounts

from tristero.types.create_match_params import CreateMatchParams, CreateMatchParamsJSON
from tristero.types.place_order_params import PlaceOrderParams, PlaceOrderParamsJSON
from tristero.types.challenge_params import ChallengeParams, ChallengeParamsJSON
from tristero.types.register_tristero_o_app_params import RegisterTristeroOAppParams, RegisterTristeroOAppParamsJSON
from tristero.types.lz_receive_type_params import LzReceiveTypeParams, LzReceiveTypeParamsJSON
from tristero.types.send_stored_params import SendStoredParams, SendStoredParamsJSON
from endpoint.types.init_nonce_params import InitNonceParams, InitNonceParamsJSON
from endpoint.types.init_send_library_params import InitSendLibraryParams, InitSendLibraryParamsJSON
from endpoint.types.init_receive_library_params import InitReceiveLibraryParams, InitReceiveLibraryParamsJSON

from tristero.accounts.admin_panel import AdminPanel
from endpoint.accounts.send_library_config import SendLibraryConfig



import time
import json
import struct

tristero_program_id = Pubkey.from_string("GAa8J7hrF7BpGezmU8oXJ5cjdUxiPdGgze8wLZn8Jt8u")
endpoint_program_id = Pubkey.from_string("76y77prsiCMvXMjuoZ5VRrhG5qYBrUMYTE5WgHqgjEn6")
executor_program_id = Pubkey.from_string("6doghB248px58JSSwG4qejQ46kFMW4AMj7vzJnWZHNZn")
send_library_program_id = Pubkey.from_string("7a4WjyR8VZ7yZz5XJAKm39BUGn5iT9CKcv2pmG9tdXVH")
price_fee_program_id = Pubkey.from_string("8ahPGPjEbpgGaZx2NV1iG5Shj7TDwvsjkEDcGWjt94TP")
dvn_program_id = Pubkey.from_string("HtEYV4xB4wvsj5fgTkcfuChYpvGYzgzwvNhgDZQNh7wW")
uln_program_id = Pubkey.from_string("7a4WjyR8VZ7yZz5XJAKm39BUGn5iT9CKcv2pmG9tdXVH")

rpc_url = "https://api.devnet.solana.com"

# Load JSON files
with open(Path("./tests/user.json"), "r") as user_file:
    user_json = json.load(user_file)

with open(Path("./tests/other.json"), "r") as other_file:
    other_json = json.load(other_file)

with open(Path("./tests/adminJson.json"), "r") as admin_file:
    admin_json = json.load(admin_file)

# Create Keypair instances from secret keys
user = Keypair.from_bytes(bytes(user_json))
other_user = Keypair.from_bytes(bytes(other_json))
admin = Keypair.from_bytes(bytes(admin_json))

LAMPORTS_PER_SOL = 1_000_000_000
ARBITRUM_EID = 40231
RECEIVER_PUBKEY = bytearray(32)

# Hexadecimal string to be converted to bytes
hex_string = '564bdffeb9582879d37e58e3af65828f37a8a2ad'

# Convert the hexadecimal string to bytes
padded_buffer = binascii.unhexlify(hex_string)

# Copy the bytes to the RECEIVER_PUBKEY bytearray starting at position 12
RECEIVER_PUBKEY[12:12 + len(padded_buffer)] = padded_buffer

payload_string = '000000000000000000000000000000000000000000000000000000000000006183247218e466e48b0ea8b8a7b99e7a53cc8153766c6ac5c88076290adee38d513b442cb3912157f13a933d0134282d032b5ffecd01a2dbf1b7790608df002ea70000000000000000000000006fcfc05c7963d0fb23c706450c7c72adda8fbf60'
payload_buffer = binascii.unhexlify(payload_string)

# Print the result
print("receiverPubKey =>", RECEIVER_PUBKEY)

def get_order_pda(order_id):
    order_id_buffer = order_id.to_bytes(8, byteorder="big")
    seeds = [
        b"order",
        order_id_buffer
    ]
    return Pubkey.find_program_address(seeds, tristero_program_id)[0]

def get_refund_token_account_pda(pubkey):
    seeds = [
        b"refund_account",
        bytes(pubkey)
    ]
    return Pubkey.find_program_address(seeds, tristero_program_id)[0]

def get_admin_panel():
    seeds = [
        b"admin_panel"
    ]
    return Pubkey.find_program_address(seeds, tristero_program_id)[0]

def get_oapp_pda(authority):
    (distributor, bump) = Pubkey.find_program_address(
        [b"OApp", bytes(authority)],
        endpoint_program_id,
    )
    return distributor

def get_uln_pda():
    (distributor, bump) = Pubkey.find_program_address(
        [b"MessageLib"],
        uln_program_id,
    )
    return distributor

def get_tristero_oapp():
    (distributor, bump) = Pubkey.find_program_address(
        [b"TristeroOapp"],
        tristero_program_id,
    )
    return distributor

def get_tristero_oapp_bump():
    (distributor, bump) = Pubkey.find_program_address(
        [b"TristeroOapp"],
        tristero_program_id,
    )
    return bump

def get_message_lib_pda():
    (distributor, bump) = Pubkey.find_program_address(
        [b"MessageLib"],
        endpoint_program_id,
    )
    return distributor

def get_message_lib_info_pda(pubkey):
    (distributor, bump) = Pubkey.find_program_address(
        [b"MessageLib", bytes(pubkey)],
        endpoint_program_id,
    )
    return distributor

def get_oapp_registry_pda(pubkey):
    (distributor, bump) = Pubkey.find_program_address(
        [b"OApp", bytes(pubkey)],
        endpoint_program_id,
    )
    return distributor

def get_receive_library_config_pda(pubkey, eid):
    eid_bytes = eid.to_bytes(4, byteorder="big")
    (distributor, bump) = Pubkey.find_program_address(
        [b"ReceiveLibraryConfig", bytes(pubkey), eid_bytes],
        endpoint_program_id,
    )
    return distributor

def get_default_send_library_config(eid):
    eid_bytes = eid.to_bytes(4, byteorder="big")
    (distributor, bump) = Pubkey.find_program_address(
        [b"SendLibraryConfig", eid_bytes],
        endpoint_program_id,
    )
    return distributor

def get_price_feed_pda():
    (distributor, bump) = Pubkey.find_program_address(
        [b"PriceFeed"],
        price_fee_program_id,
    )
    return distributor


def get_staking_panel(mint):
    (distributor, bump) = Pubkey.find_program_address(
        [b"staking_account", bytes(mint)],
        tristero_program_id,
    )
    return distributor

def get_user_pda(authority):
    (distributor, bump) = Pubkey.find_program_address(
        [b"user", bytes(authority)],
        tristero_program_id,
    )
    return distributor

def get_trade_match_pda(match_count):
    match_count_bytes = match_count.to_bytes(8, byteorder="big")
    (distributor, bump) = Pubkey.find_program_address(
        [b"trade_match", match_count_bytes],
        tristero_program_id,
    )
    return distributor

def get_send_library_config_pda(tristero_oapp, eid):
    eid_bytes = eid.to_bytes(4, byteorder="big")
    (distributor, bump) = Pubkey.find_program_address(
        [b"SendLibraryConfig", bytes(tristero_oapp), eid_bytes],
        endpoint_program_id,
    )
    return distributor

def get_default_send_library_config_pda(eid):
    eid_bytes = eid.to_bytes(4, byteorder="big")
    (distributor, bump) = Pubkey.find_program_address(
        [b"SendLibraryConfig", eid_bytes],
        endpoint_program_id,
    )
    return distributor

def get_send_library_info_pda(send_library_info_pubkey):
    (distributor, bump) = Pubkey.find_program_address(
        [b"MessageLib", bytes(send_library_info_pubkey)],
        endpoint_program_id,
    )
    return distributor

def get_endpoint_pda():
    return Pubkey.find_program_address(
        [b"Endpoint"],
        endpoint_program_id,
    )[0]
    
def get_nonce_pda(sender_key, eid, receiver):
    eid_buffer = eid.to_bytes(4, byteorder="big")
    seeds = [
        b"Nonce",
        bytes(sender_key),
        eid_buffer,
        bytes(receiver)
    ]
    
    return Pubkey.find_program_address(seeds, endpoint_program_id)[0]

def get_pending_inbound_nonce_pda(sender_key, eid, receiver):
    eid_buffer = eid.to_bytes(4, byteorder="big")
    seeds = [
        b"PendingNonce",
        bytes(sender_key),
        eid_buffer,
        bytes(receiver)
    ]
    
    return Pubkey.find_program_address(seeds, endpoint_program_id)[0]

def get_event_authority_pda():
    (distributor, bump) = Pubkey.find_program_address(
        [b"__event_authority"],
        endpoint_program_id,
    )
    return distributor

def get_uln_program_pda():
    (distributor, bump) = Pubkey.find_program_address(
        [b"MessageLib"],
        uln_program_id,
    )
    return distributor

def get_send_config_pda(eid, sender_addr):
    eid_buffer = eid.to_bytes(4, byteorder="big")
    (distributor, bump) = Pubkey.find_program_address(
        [b"SendConfig", eid_buffer, bytes(sender_addr)],
        uln_program_id,
    )
    return distributor

def get_default_send_config_pda(eid):
    eid_buffer = eid.to_bytes(4, byteorder="big")
    (distributor, bump) = Pubkey.find_program_address(
        [b"SendConfig", eid_buffer],
        uln_program_id,
    )
    return distributor

def get_uln_event_authority_pda():
    (distributor, bump) = Pubkey.find_program_address(
        [b"__event_authority"],
        uln_program_id,
    )
    return distributor

def get_executor_pda_deriver():
    (distributor, bump) = Pubkey.find_program_address(
        [b"ExecutorConfig"],
        executor_program_id,
    )
    return distributor

def get_price_fee_program_pda():
    (distributor, bump) = Pubkey.find_program_address(
        [b"PriceFeed"],
        price_fee_program_id,
    )
    return distributor

def get_dvn_derive_config_pda():
    (distributor, bump) = Pubkey.find_program_address(
        [b"DvnConfig"],
        dvn_program_id,
    )
    return distributor

def get_lz_receive_types_pda(oapp_config):
    (distributor, bump) = Pubkey.find_program_address(
        [b"LzReceiveTypes", bytes(oapp_config)],
        tristero_program_id,
    )
    return distributor

async def main():
    # Connect to the Solana testnet
    solana_client = Client("https://api.devnet.solana.com")
    ##context = await start_anchor(Path("../"))
    
    # Read the generated IDL.
    with Path("./target/idl/tristero.json").open() as f:
        raw_idl = f.read()
    idl = Idl.from_json(raw_idl)
    
    client = AsyncClient("https://api.devnet.solana.com")
    provider = Provider(client, Wallet.local())
    
    async with Program(idl, tristero_program_id, provider) as program:
        print(f"program: ", program)
        tristero_oapp_pubkey = get_tristero_oapp()
        
        # print(f"--------------------------Register New Oapp------------------------------")
        # register_oapp_accounts: RegisterTristeroOappAccounts = {
        #     "payer": admin.pubkey(),
        #     "oapp": tristero_oapp_pubkey,
        #     "oapp_registry": get_oapp_registry_pda(tristero_oapp_pubkey),
        #     "event_authority": get_event_authority_pda(),
        #     "endpoint_program": endpoint_program_id
        # }
        
        # register_tristero_oapp_params_json : RegisterTristeroOAppParamsJSON = {
        #     "delegate": str(admin.pubkey()),
        #     "admin_wallet": str(admin.pubkey()),
        #     "payment_wallet": str(admin.pubkey())
        # }
        
        # register_tristero_oapp_params = RegisterTristeroOAppParams.from_json(register_tristero_oapp_params_json)
        # register_tristero_oapp_ix = register_tristero_oapp(
        #     {
        #         "params": register_tristero_oapp_params
        #     },
        #     register_oapp_accounts,
        #     tristero_program_id
        # )
        
        # latest_blockhash = solana_client.get_latest_blockhash()
        # blockhash = latest_blockhash.value.blockhash
        # signers = [admin]
        
        # txn = Transaction(recent_blockhash=blockhash, fee_payer=admin.pubkey())
        # txn.add(set_compute_unit_limit(2000000))
        # txn.add(register_tristero_oapp_ix)
        
        # register_tristero_oapp_tx = solana_client.send_transaction(txn, *signers, opts=TxOpts(skip_confirmation=False, preflight_commitment=Confirmed)).value
        # print(f"register_tristero_oapp_tx: {register_tristero_oapp_tx}")
        # print(f"tristero_oapp: ", tristero_oapp_pubkey)
        
        
        
        admin_panel_account = await program.account["AdminPanel"].fetch(tristero_oapp_pubkey)
        
        print(f"get_nonce_pda(tristero_oapp_pubkey, ARBITRUM_EID, RECEIVER_PUBKEY) => {get_nonce_pda(tristero_oapp_pubkey, ARBITRUM_EID, RECEIVER_PUBKEY)}")
        sol_treasury = get_sol_treasury()
        print(f"sol_treasury: {sol_treasury}")
        send_library_config = get_send_library_config_pda(tristero_oapp_pubkey, ARBITRUM_EID)
        default_send_library_config = get_default_send_library_config(ARBITRUM_EID)
        
        send_library_info_account = await SendLibraryConfig.fetch(client, default_send_library_config, program_id = endpoint_program_id)
        
        send_library_info_pubkey = send_library_info_account.message_lib
        
        send_instruction_remaining_accounts = [
            AccountMeta( #0
                pubkey = Pubkey.from_string("76y77prsiCMvXMjuoZ5VRrhG5qYBrUMYTE5WgHqgjEn6"),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #1
                pubkey = tristero_oapp_pubkey,
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #2
                pubkey = Pubkey.from_string("7a4WjyR8VZ7yZz5XJAKm39BUGn5iT9CKcv2pmG9tdXVH"),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #3
                pubkey = send_library_config,
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #4
                pubkey = default_send_library_config,
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #5
                pubkey = get_send_library_info_pda(send_library_info_pubkey),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #6
                pubkey = get_endpoint_pda(),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #7
                pubkey = get_nonce_pda(tristero_oapp_pubkey, ARBITRUM_EID, RECEIVER_PUBKEY),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #8
                pubkey = get_event_authority_pda(),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #9
                pubkey = endpoint_program_id,
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #10
                pubkey = get_uln_program_pda(),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #11
                pubkey = get_send_config_pda(ARBITRUM_EID, tristero_oapp_pubkey),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #12
                pubkey = get_default_send_config_pda(ARBITRUM_EID),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #13
                pubkey = user.pubkey(),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #14
                pubkey = user.pubkey(),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #15
                pubkey = SYS_PROGRAM_ID,
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #16
                pubkey = get_uln_event_authority_pda(),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #17
                pubkey = uln_program_id,
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #18
                pubkey = executor_program_id,
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #19
                pubkey = get_executor_pda_deriver(),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #20
                pubkey = price_fee_program_id,
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #21
                pubkey = get_price_fee_program_pda(),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #22
                pubkey = dvn_program_id,
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #23
                pubkey = get_dvn_derive_config_pda(),
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #24
                pubkey = price_fee_program_id,
                is_signer = False,
                is_writable =  True
            ),
            AccountMeta( #25
                pubkey = get_price_fee_program_pda(),
                is_signer = False,
                is_writable =  True
            )
        ]
        
        mint_addr = Pubkey.from_string("4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU")
        
        order_id = admin_panel_account.order_count
        trade_match_id = admin_panel_account.match_count
        
        erc20_addr = binascii.unhexlify('75faf114eafb1bdbe2f0316df893fd58ce46aa4d')
        arb_wallet_addr = binascii.unhexlify('De7014167c36c39aAfb56aA0Bd87776d8911369A')
        
        # print(f"-----------------------Init Send Library---------------------------")
        # init_send_library_accounts: InitSendLibraryAccounts = {
        #     "delegate": admin.pubkey(),
        #     "oapp_registry": get_oapp_registry_pda(tristero_oapp_pubkey),
        #     "send_library_config": get_send_library_config_pda(tristero_oapp_pubkey, ARBITRUM_EID),
        # }
        
        # init_send_library_params_json : InitSendLibraryParamsJSON = {
        #     "sender":  str(tristero_oapp_pubkey),
        #     "eid": ARBITRUM_EID,
        # }
        
        # init_send_library_params = InitSendLibraryParams.from_json(init_send_library_params_json)
        
        # init_send_library_ix = init_send_library(
        #     {
        #         "params": init_send_library_params
        #     },
        #     init_send_library_accounts,
        #     endpoint_program_id
        # )
        
        # latest_blockhash = solana_client.get_latest_blockhash()
        # blockhash = latest_blockhash.value.blockhash
        # signers = [admin]
        
        # txn = Transaction(recent_blockhash=blockhash, fee_payer=admin.pubkey())
        # txn.add(set_compute_unit_limit(2000000))
        # txn.add(init_send_library_ix)
        
        # init_send_library_tx = solana_client.send_transaction(txn, *signers, opts=TxOpts(skip_confirmation=False, preflight_commitment=Confirmed)).value
        # print(f"init_send_library_tx: {init_send_library_tx}")
        
        # print(f"-----------------------Init Receive Library---------------------------")
        # init_receive_library_accounts: InitReceiveLibraryAccounts = {
        #     "delegate": admin.pubkey(),
        #     "oapp_registry": get_oapp_registry_pda(tristero_oapp_pubkey),
        #     "receive_library_config": get_receive_library_config_pda(tristero_oapp_pubkey, ARBITRUM_EID),
        # }
        
        # init_receive_library_params_json : InitReceiveLibraryParamsJSON = {
        #     "receiver": str(tristero_oapp_pubkey),
        #     "eid": ARBITRUM_EID,
        # }
        
        # init_receive_library_params = InitReceiveLibraryParams.from_json(init_receive_library_params_json)
        
        # init_receive_library_ix = init_receive_library(
        #     {
        #         "params": init_receive_library_params
        #     },
        #     init_receive_library_accounts,
        #     endpoint_program_id
        # )
        
        # latest_blockhash = solana_client.get_latest_blockhash()
        # blockhash = latest_blockhash.value.blockhash
        # signers = [admin]
        
        # txn = Transaction(recent_blockhash=blockhash, fee_payer=admin.pubkey())
        # txn.add(set_compute_unit_limit(2000000))
        # txn.add(init_receive_library_ix)
        
        # init_receive_library_tx = solana_client.send_transaction(txn, *signers, opts=TxOpts(skip_confirmation=False, preflight_commitment=Confirmed)).value
        # print(f"init_receive_library_tx: {init_receive_library_tx}")
        
        # print(f"-----------------------Init Nonce---------------------------")
        # print(f"get_nonce_pda(tristero_oapp_pubkey, ARBITRUM_EID, RECEIVER_PUBKEY) => {get_nonce_pda(tristero_oapp_pubkey, ARBITRUM_EID, RECEIVER_PUBKEY)}")
        # init_nonce_accounts: InitNonceAccounts = {
        #     "delegate": admin.pubkey(),
        #     "oapp_registry": get_oapp_registry_pda(tristero_oapp_pubkey),
        #     "nonce": get_nonce_pda(tristero_oapp_pubkey, ARBITRUM_EID, RECEIVER_PUBKEY),
        #     "pending_inbound_nonce": get_pending_inbound_nonce_pda(tristero_oapp_pubkey, ARBITRUM_EID, RECEIVER_PUBKEY)
        # }
        
        # init_nonce_params_json : InitNonceParamsJSON = {
        #     "local_oapp": str(tristero_oapp_pubkey),
        #     "remote_eid": ARBITRUM_EID,
        #     "remote_oapp": RECEIVER_PUBKEY
        # }
        
        # init_nonce_params = InitNonceParams.from_json(init_nonce_params_json)
        
        # init_nonce_ix = init_nonce(
        #     {
        #         "params": init_nonce_params
        #     },
        #     init_nonce_accounts,
        #     endpoint_program_id
        # )
        
        # latest_blockhash = solana_client.get_latest_blockhash()
        # blockhash = latest_blockhash.value.blockhash
        # signers = [admin]
        
        # txn = Transaction(recent_blockhash=blockhash, fee_payer=admin.pubkey())
        # txn.add(set_compute_unit_limit(2000000))
        # txn.add(init_nonce_ix)
        
        # init_nonce_tx = solana_client.send_transaction(txn, *signers, opts=TxOpts(skip_confirmation=False, preflight_commitment=Confirmed)).value
        # print(f"init_nonce_tx: {init_nonce_tx}")
        
        # print(f"---------------------Init Oft-Config------------------------")
        # print(f"get_send_library_info_pda(send_library_info_pubkey) => {get_send_library_info_pda(send_library_info_pubkey)}")
        # register_config_accounts: RegisterConfigAccounts = {
        #     "payer": admin.pubkey(),
        #     "oapp_config": tristero_oapp_pubkey,
        #     "lz_receive_types_accounts": get_lz_receive_types_pda(tristero_oapp_pubkey)
        # }
        
        # register_config_ix = register_config(
        #     {
        #         "param_pubkey": get_send_library_info_pda(send_library_info_pubkey)
        #     },
        #     register_config_accounts,
        #     tristero_program_id
        # )
        
        # latest_blockhash = solana_client.get_latest_blockhash()
        # blockhash = latest_blockhash.value.blockhash
        # signers = [admin]
        
        # txn = Transaction(recent_blockhash=blockhash, fee_payer=admin.pubkey())
        # txn.add(set_compute_unit_limit(2000000))
        # txn.add(register_config_ix)
        
        # register_config_tx = solana_client.send_transaction(txn, *signers, opts=TxOpts(skip_confirmation=False, preflight_commitment=Confirmed)).value
        # print(f"register_config_tx: {register_config_tx}")
        
        # print(f"-----------------------Place Order--------------------------")
        # place_order_accounts: PlaceOrderAccounts = {
        #     "authority": user.pubkey(),
        #     "admin_panel": tristero_oapp_pubkey,
        #     "sol_treasury": get_sol_treasury(),
        #     "token_mint": mint_addr,
        #     "token_account": Pubkey.from_string("6RzJ96TziaKHitum3KW5524D6GbvqqYJAeaNfQyicmEx"),
        #     "staking_account": get_staking_panel(mint_addr),
        #     "order": get_order_pda(order_id)
        # }
        
        # place_order_params_json : PlaceOrderParamsJSON = {
        #     "source_sell_amount": 100,
        #     "min_sell_amount": 10,
        #     "dest_token_mint": erc20_addr,
        #     "dest_buy_amount": 100,
        #     "order_id": order_id,
        #     "eid": ARBITRUM_EID
        # }
        
        # place_order_params = PlaceOrderParams.from_json(place_order_params_json)
        
        # place_order_ix = place_order(
        #     {
        #         "params": place_order_params
        #     },
        #     place_order_accounts,
        #     tristero_program_id
        # )
        
        # latest_blockhash = solana_client.get_latest_blockhash()
        # blockhash = latest_blockhash.value.blockhash
        # signers = [user]
        
        # txn = Transaction(recent_blockhash=blockhash, fee_payer=user.pubkey())
        # txn.add(set_compute_unit_limit(2000000))
        # txn.add(place_order_ix)
        
        # place_order_tx = solana_client.send_transaction(txn, *signers, opts=TxOpts(skip_confirmation=False, preflight_commitment=Confirmed)).value
        # print(f"place_order_tx: {place_order_tx}")
        # print(f"order_id: :{order_id}")
        
        # # calling create_match instruction
        # print(f"-----------------------Create Match--------------------------")
        # create_match_accounts : CreateMatchAccounts = {
        #     "authority": admin.pubkey(),
        #     "admin_panel": tristero_oapp_pubkey,
        #     "order": get_order_pda(order_id),
        #     "trade_match": get_trade_match_pda(trade_match_id)
        # }
        
        # create_match_params_json : CreateMatchParamsJSON = {
        #     "src_index": order_id,
        #     "dst_index": 2,
        #     "src_quantity": 100,
        #     "dst_quantity": 100,
        #     "trade_match_id": trade_match_id,
        #     "arb_source_token_addr": arb_wallet_addr
        # }
        
        # create_match_params = CreateMatchParams.from_json(create_match_params_json)
        
        # create_match_ix = create_match(
        #     {
        #         "params": create_match_params
        #     },
        #     create_match_accounts,
        #     tristero_program_id
        # )
        # latest_blockhash = solana_client.get_latest_blockhash()
        # blockhash = latest_blockhash.value.blockhash
        # signers = [admin]
        
        # txn = Transaction(recent_blockhash=blockhash, fee_payer=admin.pubkey())
        # txn.add(set_compute_unit_limit(2000000))
        # txn.add(create_match_ix)
        
        # create_match_tx = solana_client.send_transaction(txn, *signers, opts=TxOpts(skip_confirmation=False, preflight_commitment=Confirmed)).value
        # print(f"create_match_tx: {create_match_tx}")
        # print(f"match_id: {trade_match_id}")
        
        trade_match_id = 16
        
        # print(f"-------------------------Challenge----------------------------")
        # challenge_accounts : ChallengeAccounts = {
        #     "authority": user.pubkey(),
        #     "admin_panel": tristero_oapp_pubkey,
        #     "trade_match": get_trade_match_pda(trade_match_id)
        # }
        
        # challenge_params_json : ChallengeParamsJSON = {
        #     "trade_match_id": trade_match_id,
        #     "tristero_oapp_bump": get_tristero_oapp_bump(),
        #     "source_token_address_in_arbitrum_chain": arb_wallet_addr,
        #     "receiver": RECEIVER_PUBKEY
        # }
        
        # challenge_params = ChallengeParams.from_json(challenge_params_json)
        
        # challenge_ix = challenge(
        #     {
        #         "params": challenge_params
        #     },
        #     challenge_accounts,
        #     tristero_program_id,
        #     send_instruction_remaining_accounts
        # )
        # latest_blockhash = solana_client.get_latest_blockhash()
        # blockhash = latest_blockhash.value.blockhash
        # signers = [user]
        
        # txn = Transaction(recent_blockhash=blockhash, fee_payer=user.pubkey())
        # txn.add(set_compute_unit_limit(2000000))
        # txn.add(challenge_ix)
        
        # challenge_tx = solana_client.send_transaction(txn, *signers, opts=TxOpts(skip_confirmation=False, preflight_commitment=Confirmed)).value
        # print(f"challenge_tx: {challenge_tx}")
        
        
        
        # print(f"-------------------------Testing lz_receive_types----------------------------")
        # lz_receive_types_accounts : LzReceiveTypeParams = {
        #     "oft_config": tristero_oapp_pubkey,
        #     "message_lib": tristero_oapp_pubkey
        # }
        
        # lz_receive_types_params_json : LzReceiveTypeParamsJSON = {
        #     "src_eid": ARBITRUM_EID,
        #     "sender": RECEIVER_PUBKEY,
        #     "nonce": 1,
        #     "guid": RECEIVER_PUBKEY,
        #     "message": payload_buffer,
        #     "extra_data": [],
        # }
        
        # print(f"get_staking_panel(mint_addr) : {get_staking_panel(mint_addr)}")
        
        # lz_receive_type_params = LzReceiveTypeParams.from_json(lz_receive_types_params_json)
        
        # lz_receive_types_ix = lz_receive_types(
        #     {
        #         "params": lz_receive_type_params
        #     },
        #     lz_receive_types_accounts,
        #     tristero_program_id
        # )
        # latest_blockhash = solana_client.get_latest_blockhash()
        # blockhash = latest_blockhash.value.blockhash
        # signers = [user]
        
        # txn = Transaction(recent_blockhash=blockhash, fee_payer=user.pubkey())
        # txn.add(set_compute_unit_limit(2000000))
        # txn.add(lz_receive_types_ix)
        
        # lz_receive_types_tx = solana_client.send_transaction(txn, *signers, opts=TxOpts(skip_confirmation=False, preflight_commitment=Confirmed)).value
        # print(f"lz_receive_types_tx: {lz_receive_types_tx}")
        
        # print(f"-------------------------Testing send_stored----------------------------")
        # send_stored_accounts: SendStoredAccounts = {
        #     "authority": admin.pubkey(),
        #     "oapp": tristero_oapp_pubkey,
        #     "trade_match": get_trade_match_pda(trade_match_id)
        # }
        # send_stored_params_json: SendStoredParamsJSON = {
        #     "trade_match_id": trade_match_id
        # }
        
        # send_stored_params = SendStoredParams.from_json(send_stored_params_json)
        # send_stored_ix = send_stored(
        #     {
        #         "params": send_stored_params
        #     },
        #     send_stored_accounts,
        #     tristero_program_id
        # )
        # latest_blockhash = solana_client.get_latest_blockhash()
        # blockhash = latest_blockhash.value.blockhash
        # signers = [user]
        
        # txn = Transaction(recent_blockhash=blockhash, fee_payer=user.pubkey())
        # txn.add(set_compute_unit_limit(2000000))
        # txn.add(send_stored_ix)
        
        # send_stored_tx = solana_client.send_transaction(txn, *signers, opts=TxOpts(skip_confirmation=False, preflight_commitment=Confirmed)).value
        # print(f"send_stored_tx: {send_stored_tx}")
asyncio.run(main())