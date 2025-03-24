import os
import json
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


load_dotenv()

MODEL_NAME = "gpt-4o-mini"
OPENAI_KEY  = os.getenv('OPENAI_KEY')


from src.blockchain.transaction import Web3UHelperClass
from src.memory.memory_utils import MessagesMemory

class TransactionAgent:
    def __init__(self):
        self.web3_tools = Web3UHelperClass()
        # to inteact with the user after transaction
        self.client = OpenAI(api_key=OPENAI_KEY)
        self.transaction_llm = ChatOpenAI(
        model_name=MODEL_NAME,
        openai_api_key=OPENAI_KEY,
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}}
        )
    
    def process_transaction(self, query: str, memory: MessagesMemory) -> Dict[str, Any]:
        """Process a transaction request"""

        memory.add_message("user", query)
        
        system_prompt = """
        You are a specialized agent that extracts transaction parameters from user queries for blockchain transactions.
        Your task is to identify what transaction the user wants to perform and extract relevant parameters.
        You will also make sure the transaction should be feasible in reality, even though we are doing a simulation.
        If you know their balance, use it to guess this. If not, clearly mention this transaction not work in reality. 
        
        Supported transaction types:
        1. Token swap - requires token_in, token_out, amount_in
        2. Token balance check - requires token symbol
        
        Return a JSON object with the following structure:
        {
            "transaction_type": "token_swap" | "token_balance",
            "parameters": {
                
            },
            "missing_parameters": [
             // this is if the person asks for a token 0 to token 1 swap, but does not mention how many tokens
            ]
        }
        
        If you can't determine the transaction type or parameters, return:
        {
            "transaction_type": "unknown",
            "parameters": {},
            "missing_parameters": []
        }
        """
        
        conversation_history = memory.get_message_history()

        user_message = f"""
        Based on the conversation history and the user's query, extract the necessary parameters:
        
        Conversation history:
        {conversation_history}
        
        User query: {query}
        """
        messages = [SystemMessage(content=system_prompt),
                    HumanMessage(content=user_message)]
        
        response = self.transaction_llm.invoke(messages)

        try:
            extracted_data = json.loads(response.content)

            transaction_type = extracted_data.get("transaction_type", "unknown")
            parameters = extracted_data.get("parameters", {})
            missing_parameters = extracted_data.get("missing_parameters", [])
            
            # Update extracted params in memory; for the transaction query
            for key, value in parameters.items():
                memory.update_entity(key, value)

            # followup to see if some query params are missing            
            if missing_parameters:

                # Generate a response asking for missing parameters
                response_prompt = f"""
                The user wants to perform a {transaction_type} transaction, but some parameters are missing.
                Missing parameters: {', '.join(missing_parameters)}
                
                Based on the conversation history and the current query, generate a natural language response asking for the missing parameters.
                Keep your response conversational and helpful.
                """
                print("We had a missing param")
                print(missing_parameters)
                response = self.client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that guides users through blockchain transactions."},
                        {"role": "user", "content": response_prompt}
                    ]
                )
                
                agent_response = response.choices[0].message.content
                memory.add_message("assistant", agent_response)
                
                return {
                    "transaction_type": transaction_type,
                    "parameters": parameters,
                    "missing_parameters": missing_parameters,
                    "response": agent_response,
                    "status": "incomplete"
                }
            
            result = self.execute_transaction(transaction_type, parameters)
            
            response_prompt = f"""
            The user asked: "{query}"
            
            Generate a natural language response explaining the transaction result. Make sure to not reveal any
            sensitive or private data, like private keys. 
            Also display the hash if the transaction was successful 
            {json.dumps(result, indent=2)}
            
            Format the response in a conversational, helpful manner.
            """

            # messages = [SystemMessage(content="You are a helpful assistant that explains blockchain transactions in a clear and concise way."),
            #             HumanMessage(content=response_prompt)]
            
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that explains blockchain transactions in a clear way."},
                    {"role": "user", "content": response_prompt}
                ]
            )
            agent_response = response.choices[0].message.content
            memory.add_message("assistant", agent_response)
            
            return {
                "transaction_type": transaction_type,
                "parameters": parameters,
                "result": result,
                "response": agent_response,
                "status": "complete"
            }
            
        except Exception as e:
            error_message = f"Error processing transaction: {str(e)}"
            print(error_message)

            memory.add_message("assistant", error_message)
            return {
                "error": error_message
            }
    
    def execute_transaction(self, transaction_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """ Execute the appropriate transaction based on the transaction type and parameters"""
        try:
            if transaction_type == "token_swap":
                token_in = parameters.get("token_in", "")
                token_out = parameters.get("token_out", "")
                amount_in = float(parameters.get("amount_in", 0))

                # I am not doing an actual transaction here, the gas is estimated, 
                # and most of the exchange values are hardcode
                return self.web3_tools.simulate_swap(token_in, token_out, amount_in)
            
            elif transaction_type == "token_balance":
                token_symbol = parameters.get("token_symbol", "")
                return self.web3_tools.get_token_balance(token_symbol)
            
            else:
                return {"error": "Unknown transaction type"}
                
        except Exception as e:
            return {"error": str(e)}