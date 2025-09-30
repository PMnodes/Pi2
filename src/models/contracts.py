from dataclasses import dataclass


@dataclass
class ERC20:
    abi: str = open('./assets/abi/erc20.json', 'r').read()
