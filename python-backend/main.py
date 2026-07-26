import uvicorn
import io
import torch
import numpy as np
import pandas as pd
import neurokit2 as nk
import concurrent.futures
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from scipy.signal import butter, filtfilt, resample
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from pydantic import BaseModel
from typing import List, Dict

from cv_digitizer import ECGDigitizer
from ai_engine import ECGEngine

# ==========================================
# PYDANTIC MODELS FOR CHAT
# ==========================================
class ChatRequest(BaseModel):
    message: str
    context_payload: dict
    history: List[Dict[str, str]] = []

# ==========================================
# 0. ELITE MEMORY MANAGEMENT & LIFESPAN
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Server booting up: Loading PyTorch ECG-FM model into VRAM...")
    # By loading these inside the lifespan, we prevent the ProcessPoolExecutor 
    # from accidentally duplicating them 12 times across your CPU cores.
    app.state.ai_engine = ECGEngine()
    app.state.digitizer = ECGDigitizer(target_sample_count=5000, sampling_rate=500)
    print("✅ AI Engine & Digitizer ready for requests.")
    yield
    print("🛑 Server shutting down: Clearing AI model from memory...")
    app.state.ai_engine = None
    app.state.digitizer = None

app = FastAPI(title="ECG Pipeline", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. SIGNAL FILTERING & RESAMPLING
# ==========================================
def bandpass_filter(signal, lowcut=0.5, highcut=45.0, fs=500, order=2):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, signal, axis=-1)

def preprocess_ecg_signal(signal_array: np.ndarray, target_samples: int = 5000) -> np.ndarray:
    if signal_array.ndim == 2 and signal_array.shape[0] != 12:
        signal_array = signal_array.T
        
    current_samples = signal_array.shape[1]
    
    if current_samples != target_samples:
        print(f"🔄 Resampling signal from {current_samples} to {target_samples} samples...")
        signal_array = resample(signal_array, target_samples, axis=-1)
        
    print("🧽 Applying Butterworth Bandpass Filter (0.5Hz - 45Hz)...")
    clean_signal = bandpass_filter(signal_array)
    
    return clean_signal

# ==========================================
# 2. CPU MULTI-PROCESSING PIPELINE
# ==========================================
def process_single_lead(args):
    """
    Worker function isolated to a single CPU core. 
    It receives one array, does the heavy DSP math, and returns the result safely.
    """
    lead_idx, lead_signal, sampling_rate = args
    try:
        # Aggressively clean the signal
        cleaned_ecg = nk.ecg_clean(lead_signal, sampling_rate=sampling_rate, method="neurokit")
        
        # Detect R-peaks on the enhanced signal
        peaks, info = nk.ecg_peaks(cleaned_ecg, sampling_rate=sampling_rate)
        hr = nk.ecg_rate(peaks, sampling_rate=sampling_rate, desired_length=len(cleaned_ecg))
        
        if hr is not None and len(hr) > 0:
            mean_hr = np.mean(hr)
            # Biological limits check (prevents static from being counted as a 900 BPM heartbeat)
            if not np.isnan(mean_hr) and 20 < mean_hr < 300:
                return {"lead_idx": lead_idx, "hr": int(mean_hr), "status": "success"}
                
    except Exception as e:
        # Fail silently for this specific lead so the other 11 cores can finish
        pass 
        
    return {"lead_idx": lead_idx, "hr": None, "status": "failed"}

def extract_ecg_metrics_sync(signal_array: np.ndarray, sampling_rate: int = 500) -> dict:
    """
    Analyzes all 12 leads simultaneously using an OS-level Process Pool 
    to bypass the Python GIL and maximize CPU architecture.
    """
    metrics = {
        "estimated_heart_rate_bpm": "N/A",
        "valid_leads_analyzed": 0,
        "qrs_duration_ms": "N/A",
        "pr_interval_ms": "N/A",
        "qtc_interval_ms": "N/A"
    }
    
    if signal_array.ndim == 2 and signal_array.shape[0] != 12:
        signal_array = signal_array.T
        
    # Package the 12 arrays into a list of tasks for the CPU cores
    tasks = [(i, signal_array[i], sampling_rate) for i in range(12)]
    valid_heart_rates = []
    
    print("⚡ Distributing 12-Lead DSP across CPU cores...")
    
    # Spin up the multi-core execution pool (max_workers=12 or based on CPU limits)
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = executor.map(process_single_lead, tasks)
        
        for res in results:
            if res["status"] == "success" and res["hr"] is not None:
                valid_heart_rates.append(res["hr"])
                
    if valid_heart_rates:
        # Average the heart rate across all readable leads for maximum clinical accuracy
        metrics["estimated_heart_rate_bpm"] = int(np.mean(valid_heart_rates))
        metrics["valid_leads_analyzed"] = len(valid_heart_rates)
        print(f"✅ Successfully extracted HR from {len(valid_heart_rates)} leads in parallel.")
    else:
        print("⚠️ Could not extract readable heart rate from any lead.")
        
    return metrics

# ==========================================
# 3. FASTAPI ENDPOINTS
# ==========================================
@app.get("/")
def read_root():
    return {"status": "Active", "message": "ECG Foundation Model API running."}

@app.post("/api/v1/analyze-file")
async def analyze_file(request: Request, file: UploadFile = File(...)):
    try:
        ai = request.app.state.ai_engine
        digitizer = request.app.state.digitizer
        
        file_bytes = await file.read()
        filename = file.filename
        
        # 1. Digitizer turns CSV/PDF into raw signal array
        signal_arr, metadata = digitizer.process_file(file_bytes, filename)
        
        # 2. CLEAN AND RESAMPLE THE SIGNAL
        signal_arr = preprocess_ecg_signal(signal_arr, target_samples=5000)
        
        metadata["total_samples"] = 5000
        metadata["sampling_rate_hz"] = 500
        metadata["duration_seconds"] = 10.0
        
        # ---> ASYNC CPU EXECUTION <---
        # We run the heavy ProcessPoolExecutor inside an async thread pool 
        # so FastAPI doesn't freeze up while the OS spins up the CPU cores.
        loop = asyncio.get_running_loop()
        real_metrics = await loop.run_in_executor(
            None, 
            extract_ecg_metrics_sync, 
            signal_arr, 
            500
        )
        
        if "clinical_metrics" not in metadata:
            metadata["clinical_metrics"] = {}
        metadata["clinical_metrics"].update(real_metrics)
        
        # 4. Predict using AI Foundation Model
        probabilities = ai.predict(signal_arr)
        
        # CONFIDENCE BUCKETING FOR LLAMA 3
        categorized_findings = {}
        for condition, prob in probabilities.items():
            if prob > 0.75:
                bucket = "(HIGH CONFIDENCE / PRIMARY DIAGNOSIS)"
            elif prob >= 0.35:
                bucket = "(MODERATE CONFIDENCE / SECONDARY FINDING)"
            else:
                bucket = "(LOW CONFIDENCE / BORDERLINE OBSERVATION)"
            
            categorized_findings[condition] = f"{prob} {bucket}"
        
        master_payload = {
            "file_info": metadata,
            "physiological_metrics": {
                "estimated_heart_rate": metadata["clinical_metrics"]["estimated_heart_rate_bpm"],
                "valid_leads_used_for_hr": metadata["clinical_metrics"]["valid_leads_analyzed"],
                "blood_pressure": "N/A (ECG measures electrical voltage, not arterial blood pressure)"
            },
            "disease_probabilities": categorized_findings
        }

        # 5. Generate structured report
        clinical_report = ai.explain_with_llama(master_payload)

        # 6. Extract ALL 12 LEADS for the React Grid UI
        lead_names = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
        ui_signal_traces = {}
        
        for idx, name in enumerate(lead_names):
            if idx < signal_arr.shape[0]:
                # Downsample for UI rendering speed
                ui_signal_traces[name] = signal_arr[idx][::5].tolist()

        return {
            "filename": filename,
            "status": "SUCCESS",
            "metadata": metadata,
            "probabilities": probabilities,
            "clinical_report": clinical_report,
            "signal_traces": ui_signal_traces
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing ECG file: {str(e)}")


@app.post("/api/v1/chat")
async def chat_endpoint(request: Request, chat_req: ChatRequest):
    try:
        ai = request.app.state.ai_engine
        if not ai:
            raise HTTPException(status_code=500, detail="AI Engine not loaded.")
        
        reply = ai.chat_about_report(chat_req.message, chat_req.context_payload, chat_req.history)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Required for Windows ProcessPoolExecutor compatibility
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)