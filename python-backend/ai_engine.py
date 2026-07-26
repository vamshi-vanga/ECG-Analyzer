import json
import os
import requests
import numpy as np
import torch
from pathlib import Path
import pandas as pd
# Load using fairseq_signals utilities
try:
    from fairseq_signals.utils import checkpoint_utils
except ImportError:
    checkpoint_utils = None


class ECGEngine:
    """Loads the fairseq ECG-FM model and interfaces with Ollama / Llama 3 for clinical explanations."""

    def __init__(self, checkpoint_path: str = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

        if checkpoint_path is None:
            default_path = (
                Path(__file__).resolve().parent.parent
                / "ecg-fm"
                / "mimic_iv_ecg_finetuned.pt"
            )
            checkpoint_path = str(default_path)

        print(f"Loading ECG-FM model checkpoint from {checkpoint_path} on {self.device}...")

        if checkpoint_utils is not None and os.path.exists(checkpoint_path):
            try:
                pretrained_path = str(
                    Path(__file__).resolve().parent.parent
                    / "ecg-fm"
                    / "mimic_iv_ecg_physionet_pretrained.pt"
                )

                self.model, self.cfg, self.task = checkpoint_utils.load_model_and_task(
                    checkpoint_path,
                    model_overrides={"model_path": pretrained_path}
                )
                self.model = self.model.to(self.device)
                self.model.eval()
                print("ECG-FM Model loaded successfully!")
            except Exception as e:
                print(f"Warning: Could not load model checkpoint. Error: {e}")

        # This replaces your old hardcoded self.CONDITION_LABELS
        self.labels = self._load_label_dictionary()

        self.OLLAMA_URL = "http://localhost:11434/api/generate"
        self.OLLAMA_MODEL = "llama3"

    def _load_label_dictionary(self) -> list:
        """Loads the official 71 medical classes from label_def.csv."""
        label_path = Path(__file__).resolve().parent.parent / "ecg-fm" / "label_def.csv"
        try:
            df = pd.read_csv(label_path)
            # Try to grab the full medical description column
            if 'description' in df.columns:
                return df['description'].tolist()
            elif 'SCP-ECG' in df.columns:
                return df['SCP-ECG'].tolist()
            else:
                # Fallback to the first column if headers are different
                return df.iloc[:, 0].tolist()
        except Exception as e:
            print(f"Warning: Could not load label_def.csv. Error: {e}")
            # Safe Fallback: Generate generic names so the server doesn't crash
            return [f"Cardiac Condition #{i}" for i in range(71)]

    def predict(self, signal_array: np.ndarray) -> dict:
        """Runs the PyTorch model, manages VRAM strictly, and maps outputs."""
        
        # 1. Prepare tensor safely
        if signal_array.ndim == 2 and signal_array.shape[0] != 12:
            signal_array = signal_array.T
            
        signal_array = signal_array.copy()  # Prevents negative stride error
        
        # Send array to the GPU (if available)
        signal_tensor = torch.tensor(signal_array, dtype=torch.float32).unsqueeze(0).to(self.device)

        # 2. Forward Pass (Strict GPU Memory Management)
        self.model.eval()
        
        # ---> VRAM TWEAK #1: no_grad() stops PyTorch from tracking memory for training
        with torch.no_grad():  
            outputs = self.model(source=signal_tensor)
            
            # --- Smart Extractor ---
            logits = None
            if hasattr(self.model, 'get_logits'):
                try:
                    logits = self.model.get_logits(outputs)
                except Exception:
                    pass

            if logits is None and isinstance(outputs, dict):
                target_classes = len(self.labels)
                for key, val in outputs.items():
                    if isinstance(val, torch.Tensor) and val.shape[-1] == target_classes:
                        logits = val
                        break
                if logits is None:
                    logits = outputs.get("encoder_out", outputs.get("logits", list(outputs.values())[0]))
                    
            elif logits is None and isinstance(outputs, tuple):
                logits = outputs[0]
            elif logits is None:
                logits = outputs

            # ---> VRAM TWEAK #2: detach().cpu() instantly yanks the final numbers off the GPU
            probs = torch.sigmoid(logits).squeeze().detach().cpu().numpy()
            probs = np.atleast_1d(probs).flatten()
            
        # ---> VRAM TWEAK #3: Manually destroy the massive input/output tensors
        del signal_tensor
        del outputs
        del logits
        
        # 3. Auto-Padder
        total_model_classes = len(probs)
        if len(self.labels) < total_model_classes:
            padded_labels = self.labels + [f"Unknown Class #{i}" for i in range(len(self.labels), total_model_classes)]
        else:
            padded_labels = self.labels

        # 4. Dynamic Thresholding (Eliminate False Positives)
        CONFIDENCE_THRESHOLD = 0.30
        results = {}
        sorted_indices = probs.argsort()[::-1]

        for idx in sorted_indices:
            prob = float(probs[idx])
            if prob >= CONFIDENCE_THRESHOLD:
                condition_name = padded_labels[idx]
                results[condition_name] = round(prob, 6)

        # Fallback for healthy/normal ECGs
        if not results:
            top_idx = sorted_indices[0]
            condition_name = padded_labels[top_idx]
            results[condition_name] = round(float(probs[top_idx]), 6)

        return results
        
    def explain_with_llama(self, input_data: dict) -> str:
        """Sends the ECG metadata & model probabilities to Llama 3 for a detailed clinical report."""
        
        prompt = f"""
You are an advanced Cardiology AI Specialist. Analyze the provided ECG processing data and generate a comprehensive clinical report formatted strictly in clean Markdown.

### MASTER INPUT DATA:
{json.dumps(input_data, indent=2)}

### STRICT INSTRUCTIONS:
- DO NOT output any introductory filler text (e.g., "Here is the report...").
- Start IMMEDIATELY with "### SECTION 1".
- You MUST use double line breaks between sections for readability.
- Use bullet points for lists.
- Follow this exact template:

### SECTION 1: EXTRACTED ECG PARAMETERS & METRICS
| Metric | Value |
| :--- | :--- |
| **Estimated Heart Rate** | [Insert BPM] |
| **Recording Duration** | [Insert Seconds] sec |
| **Lead Count** | [Insert Count] |
| **Sampling Frequency** | [Insert Hz] Hz |

*Note: Blood Pressure (BP) is an arterial fluid pressure measurement and cannot be derived from electrical ECG voltage tracings.*

---

### SECTION 2: CURRENT DIAGNOSIS & ACTIVE CONDITIONS
[Clearly answer whether the patient currently shows signs of heart problems based on the probabilities. Use bullet points to list the primary findings. Translate all medical terms into plain English (e.g., Premature ventricular contractions = irregular heartbeat / early beats).]

---

### SECTION 3: FUTURE CARDIAC RISK ASSESSMENT & OUTLOOK
[Provide a risk evaluation based on the findings. Use bullet points to detail potential future risks and recommend next clinical steps or medical follow-ups.]

---

### SECTION 4: EXECUTIVE SUMMARY
[Write a concise 2-3 sentence summary explaining the overall patient status, the most critical findings, and the immediate key takeaways for the clinician.]
"""

        try:
            response = requests.post(
                self.OLLAMA_URL,
                json={"model": self.OLLAMA_MODEL, "prompt": prompt, "stream": False},
                timeout=120
            )
            response.raise_for_status()
            return response.json().get("response", "No explanation generated.")
        except requests.exceptions.Timeout:
            return "Llama 3 inference timed out. Please keep Ollama loaded in RAM."
        except requests.exceptions.RequestException as e:
            return f"Llama 3 explainer service error: {str(e)}"

    def chat_about_report(self, user_message: str, context_payload: dict, history: list = []):
        """Allows real-time conversational Q&A about the ECG report using Llama 3."""
        prompt = f"""
You are an expert AI cardiology assistant. You have previously analyzed an ECG scan for this patient.
Here is the patient's clinical context and scan data:
{context_payload}

Conversation History:
{history}

User's new question: "{user_message}"

Provide a professional, clear, and medically sound response. If the user asks a dangerous or emergency question, advise immediate professional medical evaluation. Keep your answer concise and structured.
"""
        response = self.explain_with_llama({"prompt_override": prompt, "context": context_payload})
        return response