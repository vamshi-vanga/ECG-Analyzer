import io
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
import cv2
import fitz  # PyMuPDF
import numpy as np
import pandas as pd
import pytesseract
import neurokit2 as nk
from PIL import Image
from scipy.signal import resample

# Automatically configure Tesseract executable path on Windows if present
DEFAULT_WINDOWS_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if os.name == "nt" and DEFAULT_WINDOWS_TESSERACT.exists():
    pytesseract.pytesseract.tesseract_cmd = str(DEFAULT_WINDOWS_TESSERACT)

class ECGValidator:
    """Pre-processing gatekeeper to ensure data integrity before ML processing."""
    
    EXPECTED_LEADS = 12
    MINIMUM_SAMPLES = 500  # Minimum 1 second of data at 500Hz
    
    @staticmethod
    def validate_signal(signal_array: np.ndarray, file_type: str) -> bool:
        """
        Analyzes the extracted NumPy array for structural and clinical integrity.
        Raises ValueError with specific details if validation fails.
        """
        
        # 1. Check for 12 Leads (Spatial Integrity)
        if signal_array.ndim == 1:
            raise ValueError(f"Validation Failed: {file_type} contains only 1 lead. Expected {ECGValidator.EXPECTED_LEADS} leads for clinical accuracy.")
        
        num_leads = signal_array.shape[0] if signal_array.shape[0] < signal_array.shape[1] else signal_array.shape[1]
        
        if num_leads != ECGValidator.EXPECTED_LEADS:
            raise ValueError(
                f"Validation Failed: {file_type} contains {num_leads} leads. "
                f"Exactly {ECGValidator.EXPECTED_LEADS} leads are required."
            )

        # 2. Check for Missing/NaN/Infinite Values (Data Integrity)
        if np.isnan(signal_array).any():
            raise ValueError(f"Validation Failed: {file_type} contains missing values (NaNs) or blank sequences.")
            
        if np.isinf(signal_array).any():
            raise ValueError(f"Validation Failed: {file_type} contains infinite values which cannot be processed.")

        # 3. Check for Minimum Sequence Length (Temporal Integrity)
        num_samples = signal_array.shape[1] if signal_array.shape[0] == num_leads else signal_array.shape[0]
        
        if num_samples < ECGValidator.MINIMUM_SAMPLES:
            raise ValueError(
                f"Validation Failed: Sequence too short. Found {num_samples} samples. "
                f"A minimum of {ECGValidator.MINIMUM_SAMPLES} samples (1 second) is required to detect a heartbeat."
            )

        return True

class ECGDigitizer:
    """Pre-processing gatekeeper to ensure data integrity before ML processing."""
    
    EXPECTED_LEADS = 12
    MINIMUM_SAMPLES = 500  # Minimum 1 second of data at 500Hz
    
    @staticmethod
    def validate_signal(signal_array: np.ndarray, file_type: str) -> bool:
        """
        Analyzes the extracted NumPy array for structural and clinical integrity.
        Raises ValueError with specific details if validation fails.
        """
        
        # 1. Check for 12 Leads (Spatial Integrity)
        # Handle both [12, samples] and [samples, 12] shapes
        if signal_array.ndim == 1:
            raise ValueError(f"Validation Failed: {file_type} contains only 1 lead. Expected {ECGValidator.EXPECTED_LEADS} leads for clinical accuracy.")
        
        num_leads = signal_array.shape[0] if signal_array.shape[0] < signal_array.shape[1] else signal_array.shape[1]
        
        if num_leads != ECGValidator.EXPECTED_LEADS:
            raise ValueError(
                f"Validation Failed: {file_type} contains {num_leads} leads. "
                f"Exactly {ECGValidator.EXPECTED_LEADS} leads are required."
            )

        # 2. Check for Missing/NaN/Infinite Values (Data Integrity)
        if np.isnan(signal_array).any():
            raise ValueError(f"Validation Failed: {file_type} contains missing values (NaNs) or blank sequences.")
            
        if np.isinf(signal_array).any():
            raise ValueError(f"Validation Failed: {file_type} contains infinite values which cannot be processed.")

        # 3. Check for Minimum Sequence Length (Temporal Integrity)
        num_samples = signal_array.shape[1] if signal_array.shape[0] == num_leads else signal_array.shape[0]
        
        if num_samples < ECGValidator.MINIMUM_SAMPLES:
            raise ValueError(
                f"Validation Failed: Sequence too short. Found {num_samples} samples. "
                f"A minimum of {ECGValidator.MINIMUM_SAMPLES} samples (1 second) is required to detect a heartbeat."
            )

        # If all checks pass, the file is safe to process!
        return True
    """Digitizes and extracts ECG signal arrays and metadata from CSV, JSON, XML, PDF, and Image files."""

    def __init__(self, target_sample_count: int = 5000, sampling_rate: int = 500):
        self.target_sample_count = target_sample_count
        self.sampling_rate = sampling_rate

    def parse_csv(self, file_bytes: bytes) -> np.ndarray:
        df = pd.read_csv(io.BytesIO(file_bytes))
        df = df.select_dtypes(include=[np.number])
        if df.empty:
            raise ValueError("CSV file contains no numeric signal data.")
        
        data = df.to_numpy(dtype=np.float32)
        
        # Transpose if columns are leads (e.g., 12 columns, 5000 rows)
        if data.shape[1] == 12:
            data = data.T
            
        # ---> VALIDATION GATEKEEPER <---
        ECGValidator.validate_signal(data, "CSV file")
            
        return self._resample_signal(data)
        
        data = df.to_numpy(dtype=np.float32)
        # Transpose if columns are leads (e.g., 12 leads as columns)
        if data.shape[1] == 12:
            data = data.T
        elif data.ndim == 1 or data.shape[0] == 1:
            data = data.flatten()
            
        return self._resample_signal(data)

    def parse_json(self, file_bytes: bytes) -> np.ndarray:
        # ... (keep your existing JSON extraction logic here) ...
        
        signal_arr = np.array(clean_array, dtype=np.float32)
        
        # ---> VALIDATION GATEKEEPER <---
        ECGValidator.validate_signal(signal_arr, "JSON file")
        
        return self._resample_signal(signal_arr)

        if not raw_array:
            raise ValueError("Invalid JSON structure. Could not find a valid signal or lead array.")

        # Clean nested objects if present
        if isinstance(raw_array, dict):
            clean_array = list(raw_array.values())
        elif isinstance(raw_array, list):
            clean_array = []
            for item in raw_array:
                if isinstance(item, (int, float)):
                    clean_array.append(float(item))
                elif isinstance(item, dict) and "samples" in item:
                    clean_array.append(item["samples"])
                elif isinstance(item, dict):
                    clean_array.append(list(item.values())[0])
                else:
                    try:
                        clean_array.append(float(item))
                    except (ValueError, TypeError):
                        continue
        else:
            raise ValueError("Could not parse numeric samples from JSON.")

        signal_arr = np.array(clean_array, dtype=np.float32)
        return self._resample_signal(signal_arr)

    def parse_xml(self, file_bytes: bytes) -> np.ndarray:
        # ... (keep your existing XML extraction logic here) ...
        
        array = np.array(leads_data, dtype=np.float32)

        # ---> VALIDATION GATEKEEPER <---
        ECGValidator.validate_signal(array, "XML file")

        return self._resample_signal(array)

    def pdf_to_image(self, pdf_bytes: bytes) -> np.ndarray:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count < 1:
            raise ValueError("PDF document contains no pages.")

        page = doc.load_page(0)
        zoom = 300 / 72  
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def extract_ocr_scale(self, bgr_image: np.ndarray) -> float:
        gain_scale_mv = 1.0  
        try:
            gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
            ocr_text = pytesseract.image_to_string(gray).lower()
            match = re.search(r"(\d+)\s*mm\s*/\s*mv", ocr_text)
            if match:
                mm_per_mv = float(match.group(1))
                if mm_per_mv > 0:
                    gain_scale_mv = 10.0 / mm_per_mv
        except Exception:
            pass
        return gain_scale_mv

    def digitize_image(self, bgr_image: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)

        # Red grid mask elimination
        lower_red1, upper_red1 = np.array([0, 50, 50]), np.array([10, 255, 255])
        lower_red2, upper_red2 = np.array([170, 50, 50]), np.array([180, 255, 255])
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        grid_mask = cv2.bitwise_or(mask1, mask2)

        bgr_nogrid = bgr_image.copy()
        bgr_nogrid[grid_mask > 0] = [255, 255, 255]

        gray = cv2.cvtColor(bgr_nogrid, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        height, width = thresh.shape
        raw_y_signal = []

        for x in range(width):
            col = thresh[:, x]
            y_indices = np.where(col > 0)[0]
            if len(y_indices) > 0:
                raw_y_signal.append(float(np.median(y_indices)))
            else:
                if raw_y_signal:
                    raw_y_signal.append(raw_y_signal[-1])
                else:
                    raw_y_signal.append(float(height / 2))

        y_array = np.array(raw_y_signal, dtype=np.float32)
        inverted_signal = (height - y_array)

        scale_factor = self.extract_ocr_scale(bgr_image)
        baseline = np.median(inverted_signal)
        denom = max(height / 10.0, 1e-5)  
        normalized_signal = (inverted_signal - baseline) * (scale_factor / denom)

        return self._resample_signal(normalized_signal)

    def _resample_signal(self, signal_arr: np.ndarray) -> np.ndarray:
        """
        Standardizes signal length to exactly 5000 samples (10 seconds).
        Uses zero-padding for short signals instead of stretching them, 
        preserving the true heart rate and waveform shape.
        """
        if signal_arr.size == 0:
            raise ValueError("Extracted signal array is empty.")
            
        current_samples = signal_arr.shape[-1]
        
        # 1. CASE A: Shorter than 10 seconds (< 5000 samples)
        if current_samples < self.target_sample_count:
            pad_width = self.target_sample_count - current_samples
            
            if signal_arr.ndim == 2:
                # Pad only the time axis (columns), not the leads (rows)
                padded_arr = np.pad(signal_arr, ((0, 0), (0, pad_width)), mode='constant')
            else:
                # Pad a 1D single-lead array
                padded_arr = np.pad(signal_arr, (0, pad_width), mode='constant')
                
            return padded_arr.astype(np.float32)
            
        # 2. CASE B: Longer than 10 seconds (> 5000 samples)
        elif current_samples > self.target_sample_count:
            if signal_arr.ndim == 2:
                # Keep all 12 rows, but slice the columns to the target count
                return signal_arr[:, :self.target_sample_count].astype(np.float32)
            else:
                return signal_arr[:self.target_sample_count].astype(np.float32)
                
        # 3. CASE C: Exactly 10 seconds (5000 samples)
        return signal_arr.astype(np.float32)

    def extract_advanced_ecg_metrics(self, lead_signal: np.ndarray) -> dict:
        """
        Uses NeuroKit2 to clean the signal, detect R-peaks, delineate P-Q-R-S-T waves,
        and calculate standard clinical intervals in milliseconds.
        """
        metrics = {
            "estimated_heart_rate_bpm": "N/A",
            "qrs_duration_ms": "N/A",
            "pr_interval_ms": "N/A",
            "qt_interval_ms": "N/A",
            "qtc_interval_ms": "N/A"
        }

        try:
            # Extract Lead II or first available single lead
            sig = lead_signal[1] if (lead_signal.ndim == 2 and lead_signal.shape[0] > 1) else lead_signal.flatten()

            # 1. Clean the ECG signal (removes noise & baseline wander)
            cleaned = nk.ecg_clean(sig, sampling_rate=self.sampling_rate)

            # 2. Find R-peaks
            _, rpeaks = nk.ecg_peaks(cleaned, sampling_rate=self.sampling_rate)
            r_indices = rpeaks["ECG_R_Peaks"]

            if len(r_indices) < 2:
                return metrics

            # Calculate Heart Rate (BPM)
            rr_intervals_sec = np.diff(r_indices) / self.sampling_rate
            mean_rr_sec = np.mean(rr_intervals_sec)
            bpm = int(round(60.0 / mean_rr_sec))
            metrics["estimated_heart_rate_bpm"] = f"{bpm} BPM"

            # 3. Delineate P, Q, R, S, T wave boundaries
            _, waves_boundaries = nk.ecg_delineate(cleaned, rpeaks, sampling_rate=self.sampling_rate, method="delineate")

            qrs_onsets = waves_boundaries.get("ECG_R_Onsets", [])
            qrs_offsets = waves_boundaries.get("ECG_R_Offsets", [])
            p_onsets = waves_boundaries.get("ECG_P_Onsets", [])
            t_offsets = waves_boundaries.get("ECG_T_Offsets", [])

            # Compute QRS Duration (ms)
            valid_qrs = []
            for r_on, r_off in zip(qrs_onsets, qrs_offsets):
                if not np.isnan(r_on) and not np.isnan(r_off) and r_off > r_on:
                    valid_qrs.append((r_off - r_on) / self.sampling_rate * 1000)
            if valid_qrs:
                metrics["qrs_duration_ms"] = f"{round(float(np.mean(valid_qrs)), 1)} ms"

            # Compute PR Interval (ms)
            valid_pr = []
            for p_on, q_on in zip(p_onsets, qrs_onsets):
                if not np.isnan(p_on) and not np.isnan(q_on) and q_on > p_on:
                    valid_pr.append((q_on - p_on) / self.sampling_rate * 1000)
            if valid_pr:
                metrics["pr_interval_ms"] = f"{round(float(np.mean(valid_pr)), 1)} ms"

            # Compute QT & QTc Interval (ms) via Bazett's Formula
            valid_qt, valid_qtc = [], []
            for q_on, t_off in zip(qrs_onsets, t_offsets):
                if not np.isnan(q_on) and not np.isnan(t_off) and t_off > q_on:
                    qt_ms = (t_off - q_on) / self.sampling_rate * 1000
                    valid_qt.append(qt_ms)
                    valid_qtc.append(qt_ms / np.sqrt(mean_rr_sec))

            if valid_qt:
                metrics["qt_interval_ms"] = f"{round(float(np.mean(valid_qt)), 1)} ms"
                metrics["qtc_interval_ms"] = f"{round(float(np.mean(valid_qtc)), 1)} ms"

        except Exception:
            # Fallback keeps the API running without crashing if signal is too noisy
            pass

        return metrics

    def process_file(self, file_bytes: bytes, filename: str) -> tuple[np.ndarray, dict]:
        ext = filename.lower().split(".")[-1]
        
        if ext == "csv":
            signal_arr = self.parse_csv(file_bytes)
        elif ext == "json":
            signal_arr = self.parse_json(file_bytes)
        elif ext == "xml":
            signal_arr = self.parse_xml(file_bytes)
        elif ext == "pdf":
            bgr_img = self.pdf_to_image(file_bytes)
            signal_arr = self.digitize_image(bgr_img)
        elif ext in ["png", "jpg", "jpeg"]:
            nparr = np.frombuffer(file_bytes, np.uint8)
            bgr_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if bgr_img is None:
                raise ValueError("Corrupted image file.")
            signal_arr = self.digitize_image(bgr_img)
        else:
            raise ValueError(f"Unsupported file format: .{ext}")

        # --- METADATA SUMMARY ---
        samples_count = signal_arr.shape[-1]
        duration_sec = round(samples_count / self.sampling_rate, 2)
        
        # Extract advanced metrics via NeuroKit2 (Replaces hr_estimate)
        clinical_metrics = self.extract_advanced_ecg_metrics(signal_arr)

        metadata = {
            "filename": filename,
            "leads_count": signal_arr.shape[0] if signal_arr.ndim == 2 else 1,
            "total_samples": samples_count,
            "duration_seconds": duration_sec,
            "sampling_rate_hz": self.sampling_rate,
            "clinical_metrics": clinical_metrics
        }

        return signal_arr, metadata

        return signal_arr, metadata