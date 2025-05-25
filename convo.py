import ctypes
import os

# Import settings from config.py
from config import *

# --- Load RKLLM Shared Library ---
LIB_RKLLM_PATH = LIBRARY_PATH
rkllm = ctypes.CDLL(LIB_RKLLM_PATH)


# --- Constants from rkllm.h (inferred from PDF) ---
# LLMCallState (Page 2)
LLM_RUN_NORMAL = 0
LLM_RUN_FINISH = 1
LLM_RUN_WAITING = 2 # Not explicitly numbered, assuming sequence
LLM_RUN_ERROR = 3   # Not explicitly numbered, assuming sequence

# RKLLMInputType (Page 8)
RKLLM_INPUT_PROMPT = 0
RKLLM_INPUT_TOKEN = 1
RKLLM_INPUT_EMBED = 2
RKLLM_INPUT_MULTIMODAL = 3

# RKLLMInferMode (Page 10)
RKLLM_INFER_GENERATE = 0
RKLLM_INFER_GET_LOGITS = 1


# --- Structure Definitions (inferred from PDF) ---

class RKLLMExtendParam(ctypes.Structure):
    """ Corresponds to RKLLMExtendParam structure (Page 6) """
    _fields_ = [
        ("base_domain_id", ctypes.c_int32),
        ("embed_flash", ctypes.c_int8),
        ("enabled_cpus_num", ctypes.c_int8),
        ("enabled_cpus_mask", ctypes.c_uint32),
    ]

class RKLLMParam(ctypes.Structure):
    """ Corresponds to RKLLMParam structure (Page 4-7) """
    _fields_ = [
        ("model_path", ctypes.c_char_p),
        ("num_npu_core", ctypes.c_int32),
        ("use_gpu", ctypes.c_bool),
        ("max_context_len", ctypes.c_int32),
        ("max_new_tokens", ctypes.c_int32),
        ("top_k", ctypes.c_int32),
        ("top_p", ctypes.c_float),
        ("temperature", ctypes.c_float),
        ("repeat_penalty", ctypes.c_float),
        ("frequency_penalty", ctypes.c_float),
        ("mirostat", ctypes.c_int32),
        ("mirostat_tau", ctypes.c_float),
        ("mirostat_eta", ctypes.c_float),
        ("skip_special_token", ctypes.c_bool),
        ("is_async", ctypes.c_bool),
        ("img_start", ctypes.c_char_p), # For multimodal
        ("img_end", ctypes.c_char_p),   # For multimodal
        ("img_content", ctypes.c_char_p),# For multimodal
        ("extend_param", RKLLMExtendParam),
        ("n_keep", ctypes.c_int32), # Assuming int32 based on other int types
    ]

class RKLLMResult(ctypes.Structure):
    """ Corresponds to RKLLMResult structure (Page 2-3) """
    _fields_ = [
        ("text", ctypes.c_char_p),
        ("token_id", ctypes.c_int32), 
    ]

class _RKLLMInputUnion(ctypes.Union):
    """ Union part of RKLLMInput (Page 7-8) """
    _fields_ = [
        ("prompt_input", ctypes.c_char_p),
    ]

class RKLLMInput(ctypes.Structure):
    """ Corresponds to RKLLMInput structure (Page 7-8) """
    _anonymous_ = ("_input_data",) 
    _fields_ = [
        ("input_type", ctypes.c_int), 
        ("_input_data", _RKLLMInputUnion),
    ]

class RKLLMInferParam(ctypes.Structure):
    """ Corresponds to RKLLMInferParam structure (Page 10) """
    _fields_ = [
        ("mode", ctypes.c_int), 
        ("lora_params", ctypes.c_void_p), 
        ("prompt_cache_params", ctypes.c_void_p), 
        ("keep_history", ctypes.c_int), 
    ]

LLMResultCallback = ctypes.CFUNCTYPE(None, ctypes.POINTER(RKLLMResult), ctypes.c_void_p, ctypes.c_int)

@LLMResultCallback
def python_llm_callback(result_ptr, userdata, state):
    """ Python implementation of the LLMResultCallback """
    result = result_ptr.contents
    if state == LLM_RUN_NORMAL:
        if result.text:
            try:
                print(result.text.decode('utf-8', errors='replace'), end="", flush=True)
            except Exception as e:
                print(f"[Callback Error decoding text: {e}]", end="", flush=True)
    elif state == LLM_RUN_FINISH:
        pass
    elif state == LLM_RUN_ERROR:
        pass
    elif state == LLM_RUN_WAITING:
        pass 


# --- RKLLM API Function Prototypes ---
rkllm.rkllm_createDefaultParam.restype = RKLLMParam
rkllm.rkllm_createDefaultParam.argtypes = []

LLMHandle = ctypes.c_void_p 
rkllm.rkllm_init.restype = ctypes.c_int
rkllm.rkllm_init.argtypes = [ctypes.POINTER(LLMHandle), ctypes.POINTER(RKLLMParam), LLMResultCallback]

rkllm.rkllm_run.restype = ctypes.c_int
rkllm.rkllm_run.argtypes = [LLMHandle, ctypes.POINTER(RKLLMInput), ctypes.POINTER(RKLLMInferParam), ctypes.c_void_p]

rkllm.rkllm_destroy.restype = ctypes.c_int
rkllm.rkllm_destroy.argtypes = [LLMHandle]


# --- Main Inference Logic ---
def run_inference():
    # Enable RKLLM Logging from config
    os.environ['RKLLM_LOG_LEVEL'] = str(LOG_LEVEL)
    print(f"RKLLM_LOG_LEVEL set to: {os.environ['RKLLM_LOG_LEVEL']}")

    print("Starting RKLLM Interactive Conversation...")

    llm_handle = LLMHandle()

    print("Creating default parameters...")
    param = rkllm.rkllm_createDefaultParam()

    # Use model path from config
    model_path = MODEL_PATH

    if os.path.exists(model_path):
        param.model_path = model_path.encode('utf-8')
    else:
        print(f"Error: Model file not found at '{model_path}'")
        print("Please check the MODEL_PATH setting in config.py")
        return

    # Set parameters from config
    param.use_gpu = USE_GPU
    param.max_context_len = MAX_CONTEXT_LENGTH
    param.n_keep = N_KEEP
    param.is_async = IS_ASYNC
    if param.max_new_tokens == 0 and MAX_NEW_TOKENS > 0:
        param.max_new_tokens = MAX_NEW_TOKENS

    print(f"Using model: {param.model_path.decode()}")
    print(f"Parameters: max_context_len={param.max_context_len}, n_keep={param.n_keep}, use_gpu={param.use_gpu}")

    print("Initializing RKLLM model...")
    ret = rkllm.rkllm_init(ctypes.byref(llm_handle), ctypes.byref(param), python_llm_callback)
    if ret != 0:
        print(f"Error: rkllm_init failed with code {ret}")
        return
    print("RKLLM model initialized successfully.")

    # Conversation loop
    print("\nType your message and press Enter. Type 'exit' or 'quit' to end the conversation.\n")
    prompt_prefix = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n".encode('utf-8')
    history = prompt_prefix
    while True:
        user_input = input("You: ")
        if user_input.strip().lower() in ["exit", "quit"]:
            print("Exiting conversation.")
            break
        # Build prompt with conversation history and new user input
        prompt = history + b"<|im_start|>user\n" + user_input.encode('utf-8') + b"<|im_end|>\n<|im_start|>assistant\n"

        rkllm_input = RKLLMInput()
        rkllm_input.input_type = RKLLM_INPUT_PROMPT
        rkllm_input.prompt_input = ctypes.c_char_p(prompt)

        rkllm_infer_params = RKLLMInferParam()
        rkllm_infer_params.mode = RKLLM_INFER_GENERATE
        rkllm_infer_params.keep_history = 1  # Set to 1 to preserve context if supported

        print("Assistant's Response:")
        ret = rkllm.rkllm_run(llm_handle, ctypes.byref(rkllm_input), ctypes.byref(rkllm_infer_params), None)
        if ret != 0:
            print(f"\nError: rkllm_run failed with code {ret}")
        # Add user and assistant turns to history for next round
        # (If you want to append the assistant's output, you can extend this logic)
        history = prompt

    print("Destroying RKLLM model...")
    ret_destroy = rkllm.rkllm_destroy(llm_handle)
    if ret_destroy != 0:
        print(f"Error: rkllm_destroy failed with code {ret_destroy}")
    else:
        print("RKLLM model destroyed successfully.")

        print("RKLLM model destroyed successfully.")

if __name__ == "__main__":
    run_inference()
