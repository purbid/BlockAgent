import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

MODEL_NAME = "gpt-4o-mini"
OPENAI_KEY  = os.getenv('OPENAI_KEY')

from src.blockchain.graph_utils import GraphTools
from src.memory.memory_utils import MessagesMemory

class SubGraphAgent:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_KEY)
        self.graph_tools = GraphTools()
        self.subgraph_llm = ChatOpenAI(
            model_name = MODEL_NAME, 
            openai_api_key = OPENAI_KEY,
            temperature=0,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
    
    def process_query(self, query: str, memory: MessagesMemory) -> Dict[str, Any]:
        """Process a data retrieval query using The Graph"""


        print("inside subgraph query agent")
        memory.add_message("user", query)
        
        system_prompt = """
        You are a specialized agent that extarcts parameters from user queries for blockchain data retrieval.
        Your task is to identify what data the user is looking for and extract relevant parameters.
        
        Supported data types:
        1. Pool liquidity - requires token0 and token1 symbols
        2. Recent swaps - requires token symbol
        
        Return a JSON object with the following structure:
        {
            "query_type": "pool_liquidity" | "recent_swaps",
            "parameters": {
                
            }
        }
        
        If you can't determine the query type or parameters, return:
        {
            "query_type": "unknown",
            "parameters": {}
        }
        """
        
        conversation_history = memory.get_message_history()
        user_message = f"""
        Based on the conversation history and the user's query, extract the necessary parameters:
        
        Conversation history:
        {conversation_history}
        
        User query: {query}
        """
        

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        response = self.subgraph_llm.invoke(messages)

      
        try:
            extracted_data = json.loads(response.content)
            query_type = extracted_data.get("query_type", "unknown")
            parameters = extracted_data.get("parameters", {})

            result = self.execute_query(query_type, parameters)
            
            response_prompt = f"""
            The user asked: "{query}"
            
            Based on the data retrieved, generate a natural language response explaining the results:
            
            {json.dumps(result, indent=2)}
            
            Format the response in a conversational, helpful manner.
            """
            
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that explains blockchain data in a clear way."},
                    {"role": "user", "content": response_prompt}
                ]
            )
            
            agent_response = response.choices[0].message.content
            
            memory.add_message("assistant", agent_response)
            
            return {
                "query_type": query_type,
                "parameters": parameters,
                "result": result,
                "response": agent_response
            }
            
        except Exception as e:
            error_message = f"Error processing query: {str(e)}"
            memory.add_message("assistant", error_message)
            return {
                "error": error_message
            }
    
    def execute_query(self, query_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """ Execute the query on subgraph"""
        try:
            if query_type == "pool_liquidity":

                token0 = parameters.get("token0", "")
                token1 = parameters.get("token1", "")
                print("getting liquidity for {} and {}".format(token0, token1))
                result_subgraph_query  =  self.graph_tools.get_pool_liquidity(token0, token1)
                return result_subgraph_query
            
            elif query_type == "recent_swaps":
                token = parameters.get("token", "")
                limit = parameters.get("limit", 5)
                return self.graph_tools.get_recent_swaps(token, limit)
            
            else:
                return {"error": "Unknown query type"}
                
        except Exception as e:
            return {"error": str(e)}