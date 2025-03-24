import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from typing import Dict, Any, List, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


load_dotenv()

MODEL_NAME = "gpt-4-turbo"
OPENAI_KEY  = os.getenv('OPENAI_KEY')


from src.agents.subgraph_query_agent import SubGraphAgent
from src.memory.memory_utils import MessagesMemory
from src.agents.transaction_agent import TransactionAgent
from src.agents.conversation_agent import ConversationAgent


class QueryClassification(BaseModel):
    query_type: str = Field(description="Type of query: 'subgraph query', 'transaction', or 'conversation'")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")

class GraphState(TypedDict):
    """ The state class """
    query: str
    conversation_memory: MessagesMemory
    query_type: Optional[str]
    agent_response: Optional[str]
    parameters: Dict[str, Any]
    missing_parameters: List[str]
    results: Dict[str, Any]
    status: str

class BlockAgentFlow:
    def __init__(self):
        self.subgraph_agent = SubGraphAgent()
        self.transaction_agent = TransactionAgent()
        self.conversation_agent = ConversationAgent()

        self.llm = ChatOpenAI(
        model_name=MODEL_NAME,
        openai_api_key=OPENAI_KEY,
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}}
        )
      
        # define the graph
        self.workflow = self.create_workflow()


    def classify_condition_function(self, state: GraphState) -> str:
        """Return next step based on query classification."""
        if self.is_subgraph_query(state):
            return "subgraph_query"
        elif self.is_transaction_query(state):
            return "transaction_query"
        elif self.is_conversation_query(state):
            return "conversation_query"
        else:
            raise ValueError("Unknown query type")
    
    def create_workflow(self) -> StateGraph:
        """ Create the langGraph. 
            There is one coordinator agent that recieves the initial user query.
            It routes this query to either a subgraph lookup agent (uniswap graph lookup), 
            transaction agent (simulate a transaction) or a conversational agent (general QA wrt this project).
        """

        workflow = StateGraph(GraphState)


        # define the nodes
        workflow.add_node("classify_query", self.classify_query)
        workflow.add_node("process_subgraph_query", self.process_subgraph_query)
        workflow.add_node("process_transaction", self.process_transaction)
        workflow.add_node("process_conversation_query", self.process_conversation_query)
        workflow.add_node("send_response", self.send_response)
        
        # define edges

        # the coordinator either goes to uniswap subgraph lookup, fake transaction or conversation
        workflow.add_conditional_edges(
        "classify_query",
        self.classify_condition_function, 
        {
            "subgraph_query": "process_subgraph_query",
            "transaction_query": "process_transaction",
            "conversation_query": "process_conversation_query"
        }
        )

        workflow.add_edge("process_subgraph_query", "send_response")
        workflow.add_edge("process_transaction", "send_response")
        workflow.add_edge("process_conversation_query", "send_response") 

        workflow.add_edge("send_response", END)
        
        # Set the entry point
        workflow.set_entry_point("classify_query")
        compiled_workflow = workflow.compile()
        
        return compiled_workflow
    
    def classify_query(self, state: GraphState) -> GraphState:
        """ Classify the user query to route to one of the agents"""


        query = state["query"]
        memory = state["conversation_memory"]
        
        system_prompt = """
        You are a coordinator agent that routes user queries to specialized agents.
        Your task is to determine whether a query is related to data retrieval, 
        transaction execution or or general conversation. Do not just use keywords like "swap", "liquidity", etc 
        to decide the type of query, but actually understand the menaing of the user query, are they specifcally asking 
        to do a data_retrieval/transaction or just inquiring about it 
        
        Respond with a JSON object in the following format and nothing else:
        {
            "query_type": "data_retrieval" | "transaction" | "conversation",
            "confidence": 0.0 to 1.0
        }
        
        Examples:
        - "Get me the liquidity for ETH/USDC pool" -> data_retrieval
        - "Show me the current price of ETH" -> data_retrieval
        - "I want to swap 1 ETH for USDC" -> transaction
        - "Check my ETH balance" -> transaction
        - "Hello, how are you?" -> conversation
        - "Good morning" -> conversation
        - "Can you help me with something?" -> conversation
        """
        
        conversation_history = memory.get_message_history()

        user_message = f"""
        Based on this conversation history and the user query, determine the query type:
        
        Conversation history:
        {conversation_history}
        
        User query: {query}
        """
        print("classifying the user query")    
        messages = [SystemMessage(content=system_prompt),
                    HumanMessage(content=user_message)]
        
        response = self.llm.invoke(messages)

        classification_result = json.loads(response.content)

        print(classification_result)
        
        query_type = classification_result.get("query_type", "unknown")
        confidence = classification_result.get("confidence", 0.0)
        
        # I am managing memory as a list        
        memory.add_message("user", query)
        
        # I realised most queries where classification was correct were > 0.8
        if confidence < 0.7:
            requery_prompt = f"""
            I didn't quiet understand. Could you please clarify what do you wna to do? I can :

            1. Retrieve on-chain data (like token prices, liquidity, or recent transactions)
            2. Perform a transaction (like swapping tokens or checking balances)
            
            Please provide more details so I can help you better.
            """
            
            memory.add_message("assistant", requery_prompt)
            
            return {
                **state,
                "query_type": "unknown",
                "agent_response": requery_prompt,
                "status": "clarification_needed"
            }
        

        # if the thershold is met
        return {
            **state,
            "query_type": query_type,
            "status": "query_classified"
        }
    
    def is_subgraph_query(self, state: GraphState) -> bool:
        """ Check if this is a subgrapj lookup query"""

        return state["query_type"] == "data_retrieval"
    
    def is_transaction_query(self, state: GraphState) -> bool:
        """ Check if this is a transaction simulation query"""

        return state["query_type"] == "transaction"
    
    def is_conversation_query(self, state: GraphState) -> bool:
        """Check if this is a conversational query"""

        return state["query_type"] == "conversation"
    
    def process_conversation_query(self, state: GraphState) -> GraphState:
        """ Call the conversation query agent """

        query = state["query"]
        memory = state["conversation_memory"]
        return self.conversation_agent.make_conversation(query, memory, state)

    
    def process_subgraph_query(self, state: GraphState) -> GraphState:
        """ Call the subgraph query agent """
        query = state["query"]
        memory = state["conversation_memory"]
        
        # Process the query using the subgraph agent
        result = self.subgraph_agent.process_query(query, memory)
        
        return {
            **state,
            "parameters": result.get("parameters", {}),
            "results": result.get("result", {}),
            "agent_response": result.get("response", ""),
            "status": "data_processed"
        }
    
    def process_transaction(self, state: GraphState) -> GraphState:
        """ Call the transaction agent"""

        query = state["query"]
        memory = state["conversation_memory"]
        
        # Process the query using the transaction agent
        result = self.transaction_agent.process_transaction(query, memory)
        
        return {
            **state,
            "parameters": result.get("parameters", {}),
            "missing_parameters": result.get("missing_parameters", []),
            "results": result.get("result", {}),
            "agent_response": result.get("response", ""),
            "status": "transaction_processed"
        }
    
  
    def send_response(self, state: GraphState) -> GraphState:
        """Send a response based on the results."""

        # The response is already created, we just send it
        return {
            **state,
            "status": "response_generated"
        }
    
    def process(self, query: str, memory) -> Dict[str, Any]:
        """ Process a user query through the workflow. """
        if memory is None:
            memory = MessagesMemory()
        
        # Initialize the state
        state = {
            "query": query,
            "conversation_memory": memory,
            "query_type": None,
            "agent_response": None,
            "parameters": {},
            "missing_parameters": [],
            "results": {},
            "status": "initialized"
        }
        
        # Run the workflow and return the response to frontend
        result = self.workflow.invoke(state)
        
        return {
            "agent_response": result["agent_response"],
            "status": result["status"],
            "memory": memory
        }