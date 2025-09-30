from time import time
from asyncio import sleep

from eth_account.messages import encode_defunct
from web3.exceptions import TransactionNotFound
from web3.types import TxParams
from web3.eth import AsyncEth
from eth_typing import HexStr
from web3 import AsyncWeb3
from loguru import logger

from config import RETRIES, PAUSE_BETWEEN_RETRIES
from src.models.contracts import ERC20
from src.utils.common.wrappers.decorators import retry
from src.utils.data.chains import BASE
from src.utils.user.utils import Utils
from src.utils.proxy_manager import Proxy


class Account(Utils):
    def __init__(
            self,
            private_key: str,
            rpc=BASE.rpc,
            *,
            proxy: Proxy | None
    ) -> None:
        rpc = rpc or BASE.rpc
        self.private_key = private_key

        request_args = {} if proxy is None else {
            'proxy': proxy.proxy_url
        }
        self.web3 = AsyncWeb3(
            provider=AsyncWeb3.AsyncHTTPProvider(
                endpoint_uri=rpc,
                request_kwargs={**request_args, 'verify_ssl': False} if request_args else {'verify_ssl': False}
            ),
            modules={'eth': (AsyncEth,)},
        )
        self.account = self.web3.eth.account.from_key(private_key)
        self.wallet_address = self.account.address

    async def get_wallet_balance(self, is_native: bool, address: str = None) -> int:
        if not is_native:
            contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(address), abi=ERC20.abi
            )
            balance = await contract.functions.balanceOf(self.wallet_address).call()
        else:
            balance = await self.web3.eth.get_balance(self.wallet_address)

        return balance

    async def sign_transaction(self, tx: TxParams) -> HexStr:
        signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
        raw_tx_hash = await self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash = self.web3.to_hex(raw_tx_hash)
        return tx_hash

    async def wait_until_tx_finished(self, tx_hash: HexStr, max_wait_time=600) -> bool:
        start_time = time()
        while True:
            try:
                receipts = await self.web3.eth.get_transaction_receipt(tx_hash)
                status = receipts.get("status")
                if status == 1:
                    logger.success(f"Transaction confirmed!")
                    return True
                elif status is None:
                    await sleep(0.3)
                else:
                    logger.error(f"Transaction failed!")
                    return False
            except TransactionNotFound:
                if time() - start_time > max_wait_time:
                    print(f'FAILED TX: {tx_hash}')
                    return False
                await sleep(1)

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def transfer_tokens(self, is_native: bool, percentage: float):
        native_balance = await self.get_wallet_balance(is_native=True)
        if native_balance == 0:
            logger.error(f'[{self.wallet_address}] | Native balance is 0.')
            return None

        logger.debug(f'[{self.wallet_address}] | Transferring tokens...')

        # random_account = ETHAccount.create()
        amount = int(native_balance * percentage)
        tx = {
            'chainId': await self.web3.eth.chain_id,
            'from': self.wallet_address,
            'to': self.wallet_address,
            'value': amount,
            'nonce': await self.web3.eth.get_transaction_count(self.wallet_address),
            'gasPrice': int(await self.web3.eth.gas_price * 1.2)
        }
        tx.update({'gas': int(await self.web3.eth.estimate_gas(tx) * 1.5)})
        tx_hash = await self.sign_transaction(tx)
        confirmed = await self.wait_until_tx_finished(tx_hash)
        if confirmed:
            logger.success(
                f'[{self.wallet_address}] | Successfully sent {round(amount / 10 ** 18, 4)} PHRS'
                f' | TX: https://testnet.pharosscan.xyz/tx/{tx_hash}'
            )
            return tx_hash

    def get_signature(self, message: str) -> str:
        signed_message = self.web3.eth.account.sign_message(
            encode_defunct(text=message), private_key=self.private_key
        )
        signature = signed_message.signature.hex()
        return '0x' + signature
