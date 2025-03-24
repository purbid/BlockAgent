
import os
import json
import time
from web3 import Web3
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional



load_dotenv()

MODEL_NAME = "gpt-4o-mini"
PRIVATE_KEY  = os.getenv('PRIVATE_KEY')
WEB3_PROVIDER_URI = os.getenv('INFURA_KEY')



QUOTER_ABI = json.loads("""
[
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "tokenIn",
                "type": "address"
            },
            {
                "internalType": "address",
                "name": "tokenOut",
                "type": "address"
            },
            {
                "internalType": "uint24",
                "name": "fee",
                "type": "uint24"
            },
            {
                "internalType": "uint256",
                "name": "amountIn",
                "type": "uint256"
            },
            {
                "internalType": "uint160",
                "name": "sqrtPriceLimitX96",
                "type": "uint160"
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "amountOut",
                "type": "uint256"
            }
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]
""")

# This is the Uniswap ABI, since I am using a simulation, I am not using any smart contract to make a transaction
# For now, this can be thought of as a placeholder. 
UNISWAP_ABI = json.loads('''[
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "amountIn",
                "type": "uint256"
            },
            {
                "internalType": "uint24",
                "name": "fee",
                "type": "uint24"
            },
            {
                "internalType": "address",
                "name": "tokenIn",
                "type": "address"
            },
            {
                "internalType": "address",
                "name": "tokenOut",
                "type": "address"
            },
            {
                "internalType": "uint160",
                "name": "sqrtPriceLimitX96",
                "type": "uint160"
            }
        ],
        "name": "exactInputSingle",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "amountOut",
                "type": "uint256"
            }
        ],
        "stateMutability": "payable",
        "type": "function"
    }
]''')


"""
I ran a GQL query to get the token addresses of top 20 tokens on uniswap. Here are the addresses of the ones 
which I was gonna use for the demo
    {
    tokens(first: 20, orderBy: totalValueLockedUSD, orderDirection: desc) {
        id
        symbol
        name
        totalValueLockedUSD
    }
    }
"""

symbol_addr_mapping = {
    "ETH":  "0x1CcCA1cE62c62F7Be95d4A67722a8fDbed6EEcb4",
    "WETH": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", 
    "USDC": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "WBTC": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
    "USDT": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "UST" : "0xa693b19d2931d498c5b318df961919bb4aee87a5",
    "DAI" : "0x6b175474e89094c44da98b954eedeac495271d0f",
    # "MATIC": "0x7d1afa7b718fb893db30a3abc0cfc608aacfebb0",
    # "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
    "UNI": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"
}

UNISWAP_CONTRACT_ADDR = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
QUOTER_CONTRACT_ADDR = "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"


class Web3UHelperClass:
    def __init__(self):
        

        self.w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER_URI))

        if not self.w3.is_connected():
            print("Infura key probably wrong, check in .env file")

        if PRIVATE_KEY:
            self.account = self.w3.eth.account.from_key(PRIVATE_KEY)
            self.address = self.account.address
        else:
            print("you have not set any private key, which is needed to send a transaction")
    
    def get_token_balance(self, token_symbol: str) -> Dict[str, Any]:

        """ Get token balance for an address"""
        
        # takes the private key, ideally should interact with metamask wallet
        token_address = symbol_addr_mapping.get(token_symbol.upper())

        print(token_address, token_symbol)
        
        if not token_address:
            return {"error": f"Unknown token: {token_symbol}"}
        

        if token_symbol.upper() == "ETH":
            # the balance is not fetched from a smart contract, ETH of native of blockchain, balance is stored on BC
            balance_wei = self.w3.eth.get_balance(self.address)
            balance = self.w3.from_wei(balance_wei, 'ether')
            return {
                "symbol": "ETH",
                "balance": float(balance),
                "address": self.address
            }
        else:

            ## create checksum address, right now I have cc2 kind of address, it should be Cc2
            token_address = self.w3.to_checksum_address(token_address)

            #token contract object, with two methods: balanceof and decimals
            token_contract = self.w3.eth.contract(address=token_address, abi=[
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function"
                }
            ])

            # get the balance and the decimlas, to get the final balance
            balance_raw = token_contract.functions.balanceOf(self.address).call()
            decimals = token_contract.functions.decimals().call()
            balance = balance_raw / (10 ** decimals)
            
            return {
                "symbol": token_symbol.upper(),
                "balance": float(balance),
                "address": self.address
            }
    

    def simulate_swap(self, token_in: str, token_out: str, amount_in: float) -> Dict[str, Any]:
        """Simulate a token swap without actually executing it on-chain"""
        
        print("Inside simulate swap function")
        in_token_address = symbol_addr_mapping.get(token_in.upper())
        out_token_address = symbol_addr_mapping.get(token_out.upper())
        
        if not in_token_address or not out_token_address:
            return {"error": f"Unknown token: {token_in if not in_token_address else token_out}"}
        
        try:
            
            # to checksum
            in_token_checksum = self.w3.to_checksum_address(in_token_address)
            out_token_checksum = self.w3.to_checksum_address(out_token_address)
            
            # Get token decimals, I've hardcoded this for now.
            decimals = 18 

            if token_in.upper() != "ETH":
                token_contract = self.w3.eth.contract(address=in_token_checksum, abi=[
                    {
                        "constant": True,
                        "inputs": [],
                        "name": "decimals",
                        "outputs": [{"name": "", "type": "uint8"}],
                        "type": "function"
                    }
                ])
                decimals = token_contract.functions.decimals().call()
            
            # native eth blockchain unit
            amount_in_wei = int(amount_in * (10 ** decimals))
            
            # the quoter contract helps us see the exact swap tokens we will get
            quoter_contract = self.w3.eth.contract(address=QUOTER_CONTRACT_ADDR, abi=QUOTER_ABI)
            
            # taking the standard fee tier of 0.3%
            fee_tier = 3000
            
            # Get quoted amount out for the desired token
            amount_out = quoter_contract.functions.quoteExactInputSingle(
                in_token_checksum,
                out_token_checksum,
                fee_tier,
                amount_in_wei,
                0                                   
            ).call()
            
            out_decimals = 18
            if token_out.upper() != "ETH":
                out_token_contract = self.w3.eth.contract(address=out_token_checksum, abi=[
                    {
                        "constant": True,
                        "inputs": [],
                        "name": "decimals",
                        "outputs": [{"name": "", "type": "uint8"}],
                        "type": "function"
                    }
                ])
                out_decimals = out_token_contract.functions.decimals().call()
            
            amount_out_float = amount_out / (10 ** out_decimals)
            
            # this is a fake transaction hash.
            tx_hash = self.w3.keccak(text=f"simulated_swap_between_{token_in}_and_{token_out}_for_{amount_in}_at_{time.time()}")
            
            return {
                "success": True,
                "transaction_hash": tx_hash.hex(),
                "token_in": token_in.upper(),
                "token_out": token_out.upper(),
                "amount_in": amount_in,
                "amount_out": amount_out_float,
                "price_per_token": amount_out_float / amount_in if amount_in > 0 else 0,
                "fee_tier": fee_tier / 10000,
                "status": "simulated"
            }
        
        except Exception as e:
            print(f"Simulation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "token_in": token_in.upper(),
                "token_out": token_out.upper(),
                "amount_in": amount_in
            }