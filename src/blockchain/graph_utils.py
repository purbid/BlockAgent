import os
from gql import gql, Client
from dotenv import load_dotenv
from gql.transport.requests import RequestsHTTPTransport
from typing import Dict, Any, List, Optional

load_dotenv()

GRAPH_API_KEY  = os.getenv('GRAPH_KEY')
UNISWAP_V3_URL = f"https://gateway.thegraph.com/api/{GRAPH_API_KEY}/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"

class GraphQLClient:
    def __init__(self, url: str):
        transport = RequestsHTTPTransport(url=url)
        self.client = Client(transport=transport, fetch_schema_from_transport=True)
    
    def execute_query(self, query_string: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """ Execute a GraphQL query on the uniswap - V3 subgraph"""

        query = gql(query_string)
        result = self.client.execute(query, variable_values=variables)
        return result

class GraphTools:
    def __init__(self):
        self.client = GraphQLClient(UNISWAP_V3_URL)
    
    def get_pool_liquidity(self, token0: str, token1: str) -> Dict[str, Any]:
        """ Get liquidity information for a pool"""
        
        query = """
        query GetPoolData($token0: String!, $token1: String!) {
          pools(
            where: {
              token0_: {symbol_contains_nocase: $token0}, 
              token1_: {symbol_contains_nocase: $token1}
            }, 
            orderBy: totalValueLockedUSD, 
            orderDirection: desc, 
            first: 1
          ) {
            id
            token0 {
              id
              symbol
              decimals
            }
            token1 {
              id
              symbol
              decimals
            }
            totalValueLockedToken0
            totalValueLockedToken1
            totalValueLockedUSD
            volumeUSD
            feeTier
          }
        }
        """

        print(query)
        params = {"token0": token0, "token1": token1}
        result = self.client.execute_query(query, params)
        return result
    
    def get_recent_swaps(self, token_symbol: str, limit: int = 5) -> Dict[str, Any]:
        """Get recent swaps for a token"""

        query = """
        query GetRecentSwaps($symbol: String!, $limit: Int!) {
          swaps(
            where: {
              or: [
                { token0_: { symbol_contains_nocase: $symbol } }
                { token1_: { symbol_contains_nocase: $symbol } }
              ]
            }
            orderBy: timestamp
            orderDirection: desc
            first: $limit
          ) {
            id
            timestamp
            amount0
            amount1
            amountUSD
            token0 {
              symbol
            }
            token1 {
              symbol
            }
          }
        }
        """
        print(query)

        params = {"symbol": token_symbol, "limit": limit}
        result = self.client.execute_query(query, params)
        return result