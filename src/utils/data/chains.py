class Chain:
    def __init__(self, chain_id: int, rpc: str, scan: str, native_token: str) -> None:
        self.chain_id = chain_id
        self.rpc = rpc
        self.scan = scan
        self.native_token = native_token


PHAROS = Chain(
    chain_id=688688,
    rpc='https://api.zan.top/node/v1/pharos/testnet/ba0bdd8ee5db49d8997d1fe982daaaf1',
    scan='https://testnet.pharosscan.xyz/tx',
    native_token='PHRS'
)

BASE = Chain(
    chain_id=8453,
    rpc='https://base.drpc.org',
    scan='https://basescan.org/tx',
    native_token='ETH'
)

OP = Chain(
    chain_id=10,
    rpc='https://optimism.drpc.org',
    scan='https://optimistic.etherscan.io/tx',
    native_token='ETH',
)

ARB = Chain(
    chain_id=42161,
    rpc='https://arbitrum.meowrpc.com',
    scan='https://arbiscan.io/tx',
    native_token='ETH',
)

SEPOLIA = Chain(
    chain_id=11155111,
    rpc='https://ethereum-sepolia-rpc.publicnode.com',
    scan='https://sepolia.etherscan.io/tx',
    native_token='ETH'
)

chain_mapping = {
    'DOMA': DOMA,
    'BASE': BASE,
    'ARBITRUM ONE': ARB,
    'ARB': ARB,
    'OP': OP,
    'OPTIMISM': OP,
    'SEPOLIA': SEPOLIA
}
