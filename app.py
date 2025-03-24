import gradio as gr

from src.agents.workflow import BlockAgentFlow
from src.memory.memory_utils import MessagesMemory



workflow = BlockAgentFlow()
memory = MessagesMemory()


def add_user_message(query, history):
    """ Put the user message on the chat window before the bot replies"""
    history = history + [[query, None]]  
    return "", history  

def add_bot_response(history):
    """Add the bot reply on the chat window"""
    last_user_message = history[-1][0]
    
    try:
        print("here insie the bot query, making to graph ")        
        result = workflow.process(last_user_message, memory)
        bot_response = result["agent_response"]
    except Exception as e:
        bot_response = f"Error: {str(e)}"
    
    history[-1][1] = bot_response
    return history

with gr.Blocks(theme="JohnSmith9982/small_and_pretty",) as demo:
    gr.Markdown("# BlockAgent")
    gr.Markdown("""
    This is a proof-of-concept of how agentic AI can be used with blockchain to query the graph, simulate payments.
    We use the uniswap v3 subgraph to fetch on-chain data.c 
    
    ### Example queries:
        1. "Get me the liquidity for WETH/USDC pool"
        2. "I want to see the recent swaps for WETH"
        3. "I want to swap 1 WETH for USDC"
        4. "Check my WETH balance"
    """)
    
    chatbot = gr.Chatbot(height=500)
    message = gr.Textbox(placeholder="Type your query here ...", label="Ask BlockAgent")


    ### more like a reload, does not erase the memory. 

    clear_button = gr.Button("Wipe Memory")
   
    message.submit(add_user_message, inputs=[message, chatbot], outputs=[message, chatbot]) \
           .then(add_bot_response, inputs=[chatbot], outputs=[chatbot])
    
    clear_button.click(lambda: ([], []), outputs=[message, chatbot]).then(
            lambda: memory.reset(), outputs=[])
    
if __name__ == "__main__":
    demo.launch(share = True)