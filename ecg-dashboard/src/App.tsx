import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Activity, UploadCloud, Heart, AlertTriangle, ShieldCheck, Cpu, Database, Info, Bot, User, Send, FileText, Grid3X3 } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

// ============================================================================
// ISOLATED CANVAS COMPONENT: Renders a single crisp, glowing ECG lead
// ============================================================================
const LeadTrace = ({ leadName, data }: { leadName: string, data: number[] }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx || !data || data.length === 0) return

    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    const min = Math.min(...data)
    const max = Math.max(...data)
    const range = max - min || 1

    ctx.beginPath()
    ctx.strokeStyle = '#22d3ee' // Sleek Cyan-400
    ctx.lineWidth = 1.5 * window.devicePixelRatio
    ctx.lineJoin = 'round'

    // Premium glow effect
    ctx.shadowColor = 'rgba(34, 211, 238, 0.4)'
    ctx.shadowBlur = 8

    const paddingY = canvas.height * 0.15
    const drawHeight = canvas.height - (paddingY * 2)

    data.forEach((val, i) => {
      const x = (i / (data.length - 1)) * canvas.width
      const normalizedY = (val - min) / range
      const y = paddingY + drawHeight - (normalizedY * drawHeight)

      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })

    ctx.stroke()
  }, [data])

  return (
    <div className="relative h-28 bg-slate-950 border border-slate-800/80 rounded-xl overflow-hidden flex flex-col group">
      <span className="absolute top-2 left-2 z-20 text-[10px] font-bold text-cyan-400 font-mono bg-slate-900/90 border border-cyan-500/30 px-1.5 py-0.5 rounded shadow-sm">
        {leadName}
      </span>
      {/* Subtle modern grid background */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:0.75rem_0.75rem] opacity-30 z-0"></div>
      <canvas ref={canvasRef} className="w-full h-full relative z-10 transition-transform group-hover:scale-[1.02] duration-300" />
    </div>
  )
}

// ============================================================================
// MAIN DASHBOARD COMPONENT
// ============================================================================
export default function App() {
  const [showDisclaimer, setShowDisclaimer] = useState(true)
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [result, setResult] = useState<any>(null)

  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setError(null)
      setResult(null)
      setMessages([])
    }
  }

  const handleUpload = async () => {
    if (!file) return

    setLoading(true)
    setError(null)
    setResult(null)
    setMessages([])

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await axios.post('http://localhost:8000/api/v1/analyze-file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(response.data)
      setMessages([
        {
          role: 'assistant',
          content: `ECG Analyser initialized for **${file.name}**. All 12 leads processed successfully through the Foundation Model. How may I assist your clinical review today?`
        }
      ])
    } catch (err) {
      setError('Connection refused. Verify Python backend and FastAPI worker status.')
    } finally {
      setLoading(false)
    }
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputMessage.trim() || !result || chatLoading) return

    const userText = inputMessage
    setInputMessage('')
    const newMessages: Message[] = [...messages, { role: 'user', content: userText }]
    setMessages(newMessages)
    setChatLoading(true)

    try {
      const payload = { message: userText, context_payload: result, history: messages }
      const res = await axios.post('http://localhost:8000/api/v1/chat', payload)
      setMessages([...newMessages, { role: 'assistant', content: res.data.reply }])
    } catch (err) {
      setMessages([...newMessages, { role: 'assistant', content: '⚠️ Secure channel error: Failed to reach inference node.' }])
    } finally {
      setChatLoading(false)
    }
  }

  // Standard 4x3 Clinical Grid Order (Left-to-Right, Top-to-Bottom)
  const clinicalGridOrder = ['I', 'aVR', 'V1', 'V4', 'II', 'aVL', 'V2', 'V5', 'III', 'aVF', 'V3', 'V6']

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-blue-600 selection:text-white">
      
      {/* DISCLAIMER MODAL */}
      {showDisclaimer && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4">
          <div className="bg-slate-900 border border-slate-700 p-8 rounded-2xl max-w-lg shadow-2xl relative overflow-hidden transform transition-all">
            <div className="absolute top-0 left-0 w-full h-1.5 bg-amber-500"></div>
            <div className="flex items-center space-x-3 mb-5">
              <div className="bg-amber-500/10 p-2 rounded-lg">
                <AlertTriangle className="h-6 w-6 text-amber-500" />
              </div>
              <h2 className="text-xl font-bold text-white tracking-tight">Research Purposes Only</h2>
            </div>
            <div className="space-y-4 text-slate-300 text-sm leading-relaxed mb-8">
              <p>
                <strong>ECG Analyser</strong> is an experimental AI diagnostic tool designed strictly for <strong>research, educational, and computational evaluation purposes</strong>.
              </p>
              <p>
                This software is <span className="text-amber-400 font-medium">not an FDA-approved medical device</span>. The AI-generated clinical reports, classification probabilities, and LLM chat responses may contain inaccuracies and should <strong>never</strong> be used for actual patient diagnosis, treatment planning, or clinical decision-making without oversight from a licensed medical professional.
              </p>
            </div>
            <button
              onClick={() => setShowDisclaimer(false)}
              className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3.5 rounded-xl transition-all shadow-lg shadow-blue-600/20 text-sm tracking-wide"
            >
              I Understand & Agree
            </button>
          </div>
        </div>
      )}

      {/* TOP NAVIGATION BAR */}
      <header className={`bg-slate-900 border-b border-slate-800 px-8 py-4 flex items-center justify-between sticky top-0 z-50 backdrop-blur-md bg-opacity-90 ${showDisclaimer ? 'blur-sm pointer-events-none' : ''}`}>
        <div className="flex items-center space-x-4">
          <div className="bg-gradient-to-tr from-blue-600 to-cyan-500 p-2.5 rounded-xl shadow-lg shadow-blue-500/20">
            <Activity className="h-6 w-6 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white">ECG Analyser</h1>
              <span className="bg-blue-500/10 text-blue-400 border border-blue-500/20 text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider">Research Edition</span>
            </div>
            <p className="text-xs text-slate-400">Deep Learning Biosignal Diagnostic Interface</p>
          </div>
        </div>

        <div className="flex items-center space-x-6">
          <div className="hidden md:flex items-center space-x-4 text-xs text-slate-400">
            <div className="flex items-center space-x-1.5 border-r border-slate-800 pr-4">
              <Cpu className="h-4 w-4 text-indigo-400" />
              <span>PyTorch Inference</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <Database className="h-4 w-4 text-cyan-400" />
              <span>MIMIC-IV Engine</span>
            </div>
          </div>
        </div>
      </header>

      {/* MAIN WORKSPACE */}
      <main className={`flex-1 flex flex-col max-w-[1700px] w-full mx-auto p-8 space-y-8 transition-all ${showDisclaimer ? 'blur-sm pointer-events-none' : ''}`}>
        
        {/* Diagnostic Dashboard Results Grid */}
        {result && (
          <div className="space-y-8">
            
            {/* FULL WIDTH: 12-LEAD GRID */}
            <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
              <div className="flex items-center justify-between mb-6 border-b border-slate-800 pb-4">
                <div className="flex items-center space-x-3">
                  <div className="bg-cyan-500/20 p-2 rounded-lg border border-cyan-500/30">
                    <Grid3X3 className="h-5 w-5 text-cyan-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Full 12-Lead Spatial Array</h3>
                    <p className="text-xs text-slate-400 mt-0.5">Automated Butterworth Bandpass (0.5Hz–45Hz) Applied</p>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                   <span className="text-[10px] bg-slate-950 text-slate-400 border border-slate-800 px-3 py-1.5 rounded-full font-mono uppercase">Sweep Speed: Standard</span>
                   <span className="text-[10px] bg-slate-950 text-slate-400 border border-slate-800 px-3 py-1.5 rounded-full font-mono uppercase">Scale: 10mm/mV</span>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {clinicalGridOrder.map((leadName) => (
                  <LeadTrace 
                    key={leadName} 
                    leadName={leadName} 
                    data={result.signal_traces?.[leadName] || []} 
                  />
                ))}
              </div>
            </div>

            {/* LOWER SPLIT: METRICS & REPORT */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              
              {/* Left Column: Metrics & Probabilities */}
              <div className="lg:col-span-4 flex flex-col space-y-6">
                
                {/* Physiological Metrics Card */}
                <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center">
                    <Heart className="h-4 w-4 text-rose-500 mr-2" /> Extracted Telemetry
                  </h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
                      <span className="text-[11px] text-slate-400 font-medium">Heart Rate</span>
                      <p className="text-2xl font-black text-emerald-400 mt-1">
                        {result.metadata?.clinical_metrics?.estimated_heart_rate_bpm || 'N/A'} 
                        <span className="text-xs font-normal text-slate-400 ml-1">BPM</span>
                      </p>
                    </div>
                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
                      <span className="text-[11px] text-slate-400 font-medium">Duration</span>
                      <p className="text-2xl font-black text-cyan-400 mt-1">
                        {result.metadata?.duration_seconds || 10} 
                        <span className="text-xs font-normal text-slate-400 ml-1">sec</span>
                      </p>
                    </div>
                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
                      <span className="text-[11px] text-slate-400 font-medium">Sampling Rate</span>
                      <p className="text-lg font-bold text-slate-200 mt-1">{result.metadata?.sampling_rate_hz || 500} <span className="text-xs font-normal">Hz</span></p>
                    </div>
                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
                      <span className="text-[11px] text-slate-400 font-medium">Lead Topology</span>
                      <p className="text-lg font-bold text-slate-200 mt-1">{result.metadata?.leads_count || 12}-Lead</p>
                    </div>
                  </div>
                </div>

                {/* Model Probabilities Matrix */}
                <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl flex-1">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center justify-between">
                    <span className="flex items-center"><Activity className="h-4 w-4 text-cyan-400 mr-2" /> Classifications</span>
                    <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded font-mono">Confidence</span>
                  </h3>
                  <div className="space-y-3 max-h-[380px] overflow-y-auto pr-2 custom-scrollbar">
                    {Object.entries(result.probabilities || {}).map(([condition, prob]: [string, any], idx) => {
                      const percentage = (Number(prob) * 100).toFixed(1)
                      const val = Number(prob)
                      return (
                        <div key={idx} className="bg-slate-950 p-3.5 rounded-xl border border-slate-800/60">
                          <div className="flex justify-between text-xs mb-2 font-medium">
                            <span className="text-slate-200 truncate pr-2">{condition}</span>
                            <span className={`font-bold font-mono ${val > 0.75 ? 'text-emerald-400' : val > 0.35 ? 'text-amber-400' : 'text-blue-400'}`}>
                              {percentage}%
                            </span>
                          </div>
                          <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                            <div 
                              className={`h-full rounded-full transition-all duration-700 ${val > 0.75 ? 'bg-emerald-500 shadow-lg shadow-emerald-500/50' : val > 0.35 ? 'bg-amber-500' : 'bg-blue-500'}`} 
                              style={{ width: `${val * 100}%` }}
                            ></div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

              </div>

              {/* Right Column: Llama 3 Report & Chat */}
              <div className="lg:col-span-8 flex flex-col space-y-6">
                
                <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-xl flex-1 flex flex-col relative overflow-hidden min-h-[450px]">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
                    <div className="flex items-center space-x-3">
                      <div className="bg-indigo-600/20 border border-indigo-500/30 p-2 rounded-lg">
                        <FileText className="h-5 w-5 text-indigo-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold tracking-wide uppercase text-slate-200">AI Evaluation Report</h3>
                        <p className="text-xs text-slate-400">Synthesized by LLM based on diagnostic context</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2 text-xs bg-slate-950 text-slate-400 font-mono px-3 py-1.5 rounded-full border border-slate-700">
                      <Info className="h-3.5 w-3.5 text-amber-500" />
                      <span>Experimental</span>
                    </div>
                  </div>

                  <div className="bg-slate-950 border border-slate-800/80 p-8 rounded-xl flex-1 overflow-y-auto max-h-[450px] custom-scrollbar 
                    prose prose-invert prose-slate max-w-none text-sm leading-relaxed 
                    prose-headings:text-cyan-400 prose-headings:font-semibold prose-headings:tracking-wide prose-headings:mt-6 prose-headings:mb-3 
                    prose-hr:border-slate-800 prose-hr:my-6 
                    prose-table:w-full prose-table:border-collapse prose-table:text-sm prose-table:mb-6
                    prose-th:bg-slate-900 prose-th:p-3 prose-th:text-left prose-th:border-b-2 prose-th:border-slate-700
                    prose-td:p-3 prose-td:border-b prose-td:border-slate-800 
                    prose-p:text-slate-300 prose-li:text-slate-300 prose-strong:text-slate-100">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {result.clinical_report || 'Awaiting telemetry evaluation...'}
                    </ReactMarkdown>
                  </div>
                </div>

                {/* Chat Widget */}
                <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden flex flex-col h-[320px]">
                  <div className="bg-slate-900 border-b border-slate-800 px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="bg-cyan-600/20 border border-cyan-500/30 p-2 rounded-lg">
                        <Bot className="h-5 w-5 text-cyan-400" />
                      </div>
                      <div>
                        <h3 className="font-bold text-sm tracking-wide text-slate-200">Interactive Diagnostic Copilot</h3>
                        <p className="text-xs text-slate-400">Ask questions about this specific scan</p>
                      </div>
                    </div>
                  </div>

                  <div className="flex-1 p-6 overflow-y-auto space-y-4 bg-slate-950/60 custom-scrollbar">
                    {messages.map((msg, index) => (
                      <div key={index} className={`flex items-start space-x-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        {msg.role === 'assistant' && (
                          <div className="bg-slate-800 border border-slate-700 p-2 rounded-xl text-cyan-400 shadow-md shrink-0">
                            <Bot className="h-4 w-4" />
                          </div>
                        )}
                        <div className={`max-w-2xl px-5 py-3.5 rounded-2xl text-sm leading-relaxed ${msg.role === 'user' ? 'bg-blue-600 text-white rounded-br-none shadow-md' : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none shadow-md'}`}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                        </div>
                        {msg.role === 'user' && (
                          <div className="bg-slate-800 border border-slate-700 p-2 rounded-xl text-white shadow-md shrink-0">
                            <User className="h-4 w-4 text-slate-300" />
                          </div>
                        )}
                      </div>
                    ))}
                    {chatLoading && (
                      <div className="flex items-center space-x-3">
                        <div className="bg-slate-800 p-2 rounded-xl text-cyan-400 shadow-md animate-pulse">
                          <Bot className="h-4 w-4" />
                        </div>
                        <div className="bg-slate-900 border border-slate-800 px-5 py-3 rounded-2xl text-sm text-slate-400">
                          Synthesizing response...
                        </div>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>

                  <form onSubmit={handleSendMessage} className="p-4 bg-slate-900 border-t border-slate-800 flex items-center space-x-4">
                    <input 
                      type="text" 
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      placeholder="Ask about arrhythmias, intervals, or model confidence..."
                      className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-5 py-3.5 text-sm focus:outline-none focus:border-cyan-500 text-slate-100 placeholder-slate-500 shadow-inner"
                    />
                    <button 
                      type="submit"
                      disabled={!inputMessage.trim() || chatLoading}
                      className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3.5 rounded-xl disabled:opacity-50 transition-all flex items-center justify-center shadow-lg font-semibold text-xs tracking-wide uppercase"
                    >
                      <Send className="h-4 w-4 mr-2" /> Send Query
                    </button>
                  </form>
                </div>

              </div>

            </div>
          </div>
        )}

        {/* Upload Control Center - FIXED AT BOTTOM */}
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl relative overflow-hidden mt-auto">
          <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-600/5 rounded-full blur-3xl pointer-events-none"></div>
          
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 relative z-10">
            <div className="space-y-1 text-left w-full md:w-auto">
              <h2 className="text-base font-semibold text-slate-200 flex items-center">
                <ShieldCheck className="h-5 w-5 mr-2 text-cyan-500" /> Secure Data Intake
              </h2>
              <p className="text-xs text-slate-400">Upload 12-lead raw CSV telemetry. Automated Bandpass (0.5Hz–45Hz) will be applied.</p>
            </div>

            <div className="flex items-center space-x-4 w-full md:w-auto">
              <label className="flex-1 md:flex-initial flex items-center justify-center px-6 py-3 bg-slate-950 border border-slate-700 hover:border-cyan-500 rounded-xl cursor-pointer transition-all text-xs font-medium text-slate-300 shadow-inner group">
                <UploadCloud className="h-4 w-4 mr-2 text-cyan-400 group-hover:scale-110 transition-transform" />
                <span className="truncate max-w-[200px]">{file ? file.name : "Select ECG Dataset (.csv)"}</span>
                <input type="file" accept=".csv" onChange={handleFileChange} className="hidden" />
              </label>

              <button 
                onClick={handleUpload}
                disabled={!file || loading}
                className="px-8 py-3 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-blue-600/30 text-xs tracking-wide uppercase flex items-center"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                    Executing Pipeline...
                  </>
                ) : 'Analyze Biosignal'}
              </button>
            </div>
          </div>

          {error && (
            <div className="mt-4 p-3 bg-red-950/50 border border-red-800 text-red-300 rounded-xl text-xs flex items-center">
              <AlertTriangle className="h-4 w-4 mr-2 text-red-400" />
              {error}
            </div>
          )}
        </div>

      </main>
    </div>
  )
}