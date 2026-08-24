import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Square, 
  Settings as SettingsIcon, 
  Send, 
  Cpu, 
  Layers, 
  Wifi, 
  WifiOff, 
  Activity, 
  History, 
  CheckCircle, 
  XCircle, 
  AlertTriangle, 
  RefreshCw 
} from 'lucide-react';

function App() {
  // Config & Status States
  const [settings, setSettings] = useState({
    bit_time: 0.2,
    led_pin: 18,
    adc_channel: 0,
    spi_port: 0,
    spi_device: 0,
    spi_speed: 1350000,
    threshold_voltage: 1.65,
    noise_level: 0.0,
    use_mock: true
  });
  
  const [isReceiverRunning, setIsReceiverRunning] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [isTransmitting, setIsTransmitting] = useState(false);
  const [messageInput, setMessageInput] = useState('');
  
  // Telemetry States
  const [rxTelemetry, setRxTelemetry] = useState({
    voltage: 3.3,
    adc_value: 1023,
    bit: '0',
    temp_buffer: '',
    recv_state: 0,
    word: '',
    threshold: 1.65
  });
  
  const [txTelemetry, setTxTelemetry] = useState({
    bit: '',
    led_on: false,
    voltage: 3.3,
    char: '',
    progress: 0
  });

  // History & Consoles States
  const [history, setHistory] = useState([]);
  const [txConsole, setTxConsole] = useState([
    { timestamp: new Date().toLocaleTimeString(), type: 'system', message: 'Transmitter console ready.' }
  ]);
  const [rxConsole, setRxConsole] = useState([
    { timestamp: new Date().toLocaleTimeString(), type: 'system', message: 'Receiver console ready. Monitoring active.' }
  ]);

  // Oscilloscope Setup
  const canvasRef = useRef(null);
  const scopeDataRef = useRef([]); // holds historical voltages
  const maxScopePoints = 120;
  
  // WebSocket Reference
  const wsRef = useRef(null);

  // Fetch initial configuration & history
  useEffect(() => {
    fetchSettings();
    fetchHistory();
    fetchReceiverStatus();
  }, []);

  // Establish WebSocket connection
  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Monitor settings.threshold_voltage to keep telemetry threshold in sync
  useEffect(() => {
    setRxTelemetry(prev => ({ ...prev, threshold: settings.threshold_voltage }));
  }, [settings.threshold_voltage]);

  // Render Oscilloscope
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    // Set logical size equal to CSS layout size
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    let animationId;
    const draw = () => {
      ctx.fillStyle = '#04060b';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw horizontal grid lines
      ctx.strokeStyle = 'rgba(0, 229, 255, 0.05)';
      ctx.lineWidth = 1;
      const horizontalDivs = 4;
      for (let i = 1; i < horizontalDivs; i++) {
        const y = (canvas.height / horizontalDivs) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      // Draw vertical grid lines moving leftward to simulate sweep
      const verticalDivs = 10;
      for (let i = 1; i < verticalDivs; i++) {
        const x = (canvas.width / verticalDivs) * i;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }

      // Draw Threshold Voltage line (mapped 0V - 3.3V)
      const thresholdVolts = rxTelemetry.threshold;
      // 3.3V is top of canvas (y=0), 0V is bottom of canvas (y=height)
      const thresholdY = canvas.height - (thresholdVolts / 3.3) * canvas.height;
      ctx.strokeStyle = 'rgba(255, 179, 0, 0.4)';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.moveTo(0, thresholdY);
      ctx.lineTo(canvas.width, thresholdY);
      ctx.stroke();
      ctx.setLineDash([]); // Reset dash

      // Threshold tag
      ctx.fillStyle = 'rgba(255, 179, 0, 0.7)';
      ctx.font = '10px JetBrains Mono';
      ctx.fillText(`THRES: ${thresholdVolts.toFixed(2)}V`, 8, thresholdY - 4);

      // Draw waveform
      const data = scopeDataRef.current;
      if (data.length > 1) {
        ctx.strokeStyle = '#00e5ff';
        ctx.lineWidth = 3;
        ctx.shadowColor = 'rgba(0, 229, 255, 0.6)';
        ctx.shadowBlur = 8;
        ctx.beginPath();

        const step = canvas.width / (maxScopePoints - 1);
        for (let i = 0; i < data.length; i++) {
          const x = i * step;
          const y = canvas.height - (data[i] / 3.3) * canvas.height;
          if (i === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
        ctx.shadowBlur = 0; // Reset shadow
      }

      animationId = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animationId);
  }, [rxTelemetry.threshold]);

  // REST API Methods
  const fetchSettings = async () => {
    try {
      const response = await fetch('/api/settings');
      if (response.ok) {
        const data = await response.json();
        setSettings(data);
      }
    } catch (err) {
      console.error('Error fetching settings:', err);
    }
  };

  const saveSettings = async (e) => {
    if (e) e.preventDefault();
    try {
      const response = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      if (response.ok) {
        const data = await response.json();
        setSettings(data);
        addConsoleLog('tx', 'system', 'System configuration updated successfully.');
      }
    } catch (err) {
      addConsoleLog('tx', 'system', `Configuration save failed: ${err.message}`);
    }
  };

  const handleSettingChange = (key, val) => {
    setSettings(prev => ({
      ...prev,
      [key]: val
    }));
  };

  const fetchHistory = async () => {
    try {
      const response = await fetch('/api/messages');
      if (response.ok) {
        const data = await response.json();
        setHistory(data);
      }
    } catch (err) {
      console.error('Error fetching history:', err);
    }
  };

  const fetchReceiverStatus = async () => {
    try {
      const response = await fetch('/api/receiver/status');
      if (response.ok) {
        const data = await response.json();
        setIsReceiverRunning(data.is_running);
      }
    } catch (err) {
      console.error('Error fetching receiver status:', err);
    }
  };

  const toggleReceiver = async () => {
    const endpoint = isReceiverRunning ? '/api/receiver/stop' : '/api/receiver/start';
    try {
      const response = await fetch(endpoint, { method: 'POST' });
      if (response.ok) {
        const data = await response.json();
        setIsReceiverRunning(!isReceiverRunning);
        addConsoleLog('rx', 'system', `Receiver polling state changed: ${data.detail}`);
      }
    } catch (err) {
      addConsoleLog('rx', 'system', `Failed to toggle receiver: ${err.message}`);
    }
  };

  const transmitMessage = async (e) => {
    e.preventDefault();
    if (!messageInput.trim()) return;

    setIsTransmitting(true);
    addConsoleLog('tx', 'tx', `Initializing transmission request: "${messageInput}"`);
    
    try {
      const response = await fetch('/api/transmit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageInput }),
      });
      
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to submit transmission.');
      }
      
      setMessageInput('');
    } catch (err) {
      addConsoleLog('tx', 'system', `Transmission error: ${err.message}`);
      setIsTransmitting(false);
    }
  };

  // WebSocket Connection Core
  const connectWebSocket = () => {
    // Determine target WS URL. If locally served via dev server, target 8000
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host.includes('localhost:5173') ? 'localhost:8000' : window.location.host;
    const wsUrl = `${wsProtocol}//${host}/ws/lifi`;

    console.log(`Connecting to WebSocket: ${wsUrl}`);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      console.log('WebSocket connection established.');
    };

    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      handleWSMessage(payload);
    };

    ws.onclose = () => {
      setWsConnected(false);
      console.log('WebSocket connection lost. Retrying in 3 seconds...');
      setTimeout(connectWebSocket, 3000);
    };
  };

  // Dispatch WebSocket payloads
  const handleWSMessage = (payload) => {
    const { event, data } = payload;
    
    if (event === 'rx_telemetry') {
      setRxTelemetry(data);
      // Append voltage to scope queue
      scopeDataRef.current = [...scopeDataRef.current, data.voltage].slice(-maxScopePoints);
    } 
    
    else if (event === 'tx_bit') {
      setTxTelemetry(data);
      // Optional: push tx bit state to scope too if we want loopback visibility!
      scopeDataRef.current = [...scopeDataRef.current, data.voltage].slice(-maxScopePoints);
    } 
    
    else if (event === 'tx_complete') {
      setIsTransmitting(false);
      addConsoleLog('tx', 'system', `Transmission completed successfully! Sent ${data.binary_data.length} bits.`);
      addConsoleLog('tx', 'tx', `Sent raw payload: ${data.binary_data}`, true);
      fetchHistory();
    } 
    
    else if (event === 'tx_failed') {
      setIsTransmitting(false);
      addConsoleLog('tx', 'system', `Transmitter thread failed: ${data.error}`);
      fetchHistory();
    } 
    
    else if (event === 'rx_char') {
      // Partial character decoded
      addConsoleLog('rx', 'rx', `Character: '${data.char}' | Buffer Byte: ${data.binary}`);
    } 
    
    else if (event === 'rx_complete') {
      addConsoleLog('rx', 'system', `Message completed. Decoded text: "${data.text}"`);
      addConsoleLog('rx', 'rx', `Raw Bitstream: ${data.binary_data}`, true);
      fetchHistory();
    }
    
    else if (event === 'rx_failed') {
      addConsoleLog('rx', 'system', `Receiver loop encountered error: ${data.error}`);
    }
  };

  // Append items to split consoles
  const addConsoleLog = (channel, type, message, isBits = false) => {
    const timestamp = new Date().toLocaleTimeString();
    const entry = { timestamp, type, message, isBits };
    
    if (channel === 'tx') {
      setTxConsole(prev => [...prev.slice(-99), entry]);
    } else {
      setRxConsole(prev => [...prev.slice(-99), entry]);
    }

    // Auto Scroll Terminal windows
    setTimeout(() => {
      const term = document.getElementById(`${channel}-term-window`);
      if (term) term.scrollTop = term.scrollHeight;
    }, 50);
  };

  return (
    <div className="app-container">
      {/* Header Panel */}
      <header className="header">
        <div className="header-title-section">
          <h1>
            <Activity className="icon-pulse" style={{ color: 'var(--cyan)' }} /> 
            Enterprise LiFi Controller Console
          </h1>
          <p>Visible Light Communication via RPi.GPIO (LED) & MCP3008 ADC (Photodiode)</p>
        </div>
        
        <div className="system-status">
          <div className="status-indicator">
            <span className="text-secondary">API WebSocket:</span>
            {wsConnected ? (
              <span style={{ color: 'var(--cyan)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Wifi size={16} /> Online
              </span>
            ) : (
              <span style={{ color: 'var(--red)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <WifiOff size={16} /> Connecting...
              </span>
            )}
          </div>

          <div className="status-indicator">
            <span className="text-secondary">Receiver Service:</span>
            <div className={`dot ${isReceiverRunning ? 'active' : 'inactive'}`}></div>
            <span>{isReceiverRunning ? 'Listening' : 'Idle'}</span>
          </div>

          <div className="status-indicator">
            <span className="text-secondary">Transmitter:</span>
            <div className={`dot ${isTransmitting ? 'busy' : 'inactive'}`}></div>
            <span>{isTransmitting ? 'Transmitting' : 'Ready'}</span>
          </div>
        </div>
      </header>

      {/* Main Dashboard Grid */}
      <div className="dashboard-grid">
        {/* Left Column: Control Panel */}
        <aside className="main-column">
          <form className="card" onSubmit={saveSettings}>
            <div className="card-title">
              <SettingsIcon size={18} style={{ color: 'var(--cyan)' }} />
              Control Panel & Settings
            </div>

            <div className="switch-container">
              <span className="switch-label">Simulate Loopback (Mock)</span>
              <label className="switch">
                <input 
                  type="checkbox" 
                  checked={settings.use_mock} 
                  onChange={(e) => handleSettingChange('use_mock', e.target.checked)}
                />
                <span className="slider-round"></span>
              </label>
            </div>

            <div className="form-group">
              <label>
                Bit Pulse Duration 
                <span className="value">{settings.bit_time.toFixed(2)}s</span>
              </label>
              <input 
                type="range" 
                min="0.05" 
                max="1.0" 
                step="0.05"
                value={settings.bit_time} 
                onChange={(e) => handleSettingChange('bit_time', parseFloat(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label>
                Analog Signal Threshold 
                <span className="value">{settings.threshold_voltage.toFixed(2)}V</span>
              </label>
              <input 
                type="range" 
                min="0.2" 
                max="3.0" 
                step="0.05"
                value={settings.threshold_voltage} 
                onChange={(e) => handleSettingChange('threshold_voltage', parseFloat(e.target.value))}
              />
            </div>

            {settings.use_mock && (
              <div className="form-group">
                <label>
                  Simulated Channel Noise 
                  <span className="value">{(settings.noise_level * 100).toFixed(0)}%</span>
                </label>
                <input 
                  type="range" 
                  min="0.0" 
                  max="0.8" 
                  step="0.05"
                  value={settings.noise_level} 
                  onChange={(e) => handleSettingChange('noise_level', parseFloat(e.target.value))}
                />
              </div>
            )}

            <div className="form-group">
              <label>LED GPIO Pin (BCM)</label>
              <input 
                type="number" 
                className="form-control"
                value={settings.led_pin}
                disabled={!settings.use_mock}
                onChange={(e) => handleSettingChange('led_pin', parseInt(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label>ADC MCP3008 Channel</label>
              <input 
                type="number" 
                className="form-control"
                value={settings.adc_channel}
                disabled={!settings.use_mock}
                onChange={(e) => handleSettingChange('adc_channel', parseInt(e.target.value))}
              />
            </div>

            <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label>SPI Bus Port</label>
                <input 
                  type="number" 
                  className="form-control"
                  value={settings.spi_port}
                  disabled={!settings.use_mock}
                  onChange={(e) => handleSettingChange('spi_port', parseInt(e.target.value))}
                />
              </div>
              <div>
                <label>SPI Select Device</label>
                <input 
                  type="number" 
                  className="form-control"
                  value={settings.spi_device}
                  disabled={!settings.use_mock}
                  onChange={(e) => handleSettingChange('spi_device', parseInt(e.target.value))}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
              <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>
                Save Settings
              </button>
              <button 
                type="button" 
                className="btn btn-secondary" 
                onClick={fetchSettings}
                title="Reset local changes"
              >
                <RefreshCw size={14} />
              </button>
            </div>
          </form>

          {/* LED Signal visualization widget */}
          <div className="card led-visualizer">
            <div className="live-bits-title">Hardware Tx LED Status</div>
            <div className={`led-globe ${txTelemetry.led_on ? 'on' : ''}`}></div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              {txTelemetry.led_on ? 'LED EMITTING LIGHT (HIGH)' : 'LED IN DARKNESS (LOW)'}
            </div>
            {isTransmitting && (
              <div style={{ width: '100%', height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px', overflow: 'hidden', marginTop: '5px' }}>
                <div style={{ width: `${txTelemetry.progress}%`, height: '100%', background: 'var(--cyan)', transition: 'width 0.1s linear' }}></div>
              </div>
            )}
          </div>
        </aside>

        {/* Right Column: Oscilloscope and Double Console Terminals */}
        <main className="main-column">
          {/* Real-time Oscilloscope Waveform */}
          <section className="card">
            <div className="scope-header">
              <div className="card-title" style={{ margin: 0, border: 0, padding: 0 }}>
                <Activity size={18} style={{ color: 'var(--cyan)' }} />
                Real-Time Oscilloscope Waveform Monitor
              </div>
              <div className="scope-legend">
                <div className="legend-item">
                  <div className="legend-color" style={{ background: '#00e5ff' }}></div>
                  <span>Photodiode Voltage</span>
                </div>
                <div className="legend-item">
                  <div className="legend-color" style={{ borderTop: '2px dashed var(--amber)' }}></div>
                  <span>Logic Decision Threshold</span>
                </div>
              </div>
            </div>

            <div className="canvas-container">
              <canvas ref={canvasRef}></canvas>
            </div>

            <div className="telemetry-bar">
              <div className="telemetry-item">
                <div className="telemetry-label">Live Voltage</div>
                <div className="telemetry-value">
                  {rxTelemetry.voltage.toFixed(3)} V
                </div>
              </div>
              <div className="telemetry-item">
                <div className="telemetry-label">ADC 10-Bit</div>
                <div className="telemetry-value">
                  {rxTelemetry.adc_value}
                </div>
              </div>
              <div className="telemetry-item">
                <div className="telemetry-label">Logic Value</div>
                <div className="telemetry-value" style={{ color: rxTelemetry.bit === '1' ? 'var(--green)' : 'var(--red)' }}>
                  {rxTelemetry.bit}
                </div>
              </div>
              <div className="telemetry-item">
                <div className="telemetry-label">Receiver Buffer</div>
                <div className="telemetry-value" style={{ fontSize: '13px', color: 'var(--amber)' }}>
                  {rxTelemetry.temp_buffer || 'NONE'}
                </div>
              </div>
            </div>
          </section>

          {/* Double Console Terminals */}
          <section className="terminal-layout">
            {/* Transmitter console */}
            <div className="card terminal-card">
              <div className="card-title">
                <Layers size={18} style={{ color: 'var(--cyan)' }} />
                Transmitter Unit (LED BCM {settings.led_pin})
              </div>
              
              <div id="tx-term-window" className="terminal-window">
                {txConsole.map((log, i) => (
                  <div key={i} className="terminal-line">
                    <span className="timestamp">[{log.timestamp}]</span>
                    {log.type === 'system' ? (
                      <span className="prefix system-prefix">&lt;SYS&gt;</span>
                    ) : (
                      <span className="prefix tx-prefix">&lt;TX&gt;</span>
                    )}
                    {log.isBits ? (
                      <span className="bits">{log.message}</span>
                    ) : (
                      <span className="message">{log.message}</span>
                    )}
                  </div>
                ))}
              </div>

              {/* Live stream indicator bar */}
              <div className="live-bits-banner">
                <div className="live-bits-title">Current Bit:</div>
                <div className="live-bits-stream" style={{ color: 'var(--cyan)' }}>
                  {txTelemetry.bit !== '' ? `BIT: ${txTelemetry.bit} | CHAR: "${txTelemetry.char}"` : 'IDLE'}
                </div>
              </div>

              {/* Message Submit Form */}
              <form onSubmit={transmitMessage} style={{ display: 'flex', gap: '10px', marginTop: '15px' }}>
                <input 
                  type="text" 
                  className="form-control" 
                  placeholder="Enter message to transmit..."
                  style={{ flex: 1 }}
                  value={messageInput}
                  disabled={isTransmitting}
                  onChange={(e) => setMessageInput(e.target.value)}
                />
                <button type="submit" className="btn btn-primary" disabled={isTransmitting || !messageInput.trim()}>
                  <Send size={14} /> Transmit
                </button>
              </form>
            </div>

            {/* Receiver console */}
            <div className="card terminal-card">
              <div className="card-title" style={{ justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Cpu size={18} style={{ color: 'var(--green)' }} />
                  Receiver Unit (MCP3008 CH{settings.adc_channel})
                </div>
                
                <button 
                  onClick={toggleReceiver} 
                  className={`btn ${isReceiverRunning ? 'btn-danger' : 'btn-primary'}`}
                  style={{ padding: '4px 10px', fontSize: '11px' }}
                >
                  {isReceiverRunning ? (
                    <>
                      <Square size={10} /> Stop Listen
                    </>
                  ) : (
                    <>
                      <Play size={10} /> Start Listen
                    </>
                  )}
                </button>
              </div>
              
              <div id="rx-term-window" className="terminal-window">
                {rxConsole.map((log, i) => (
                  <div key={i} className="terminal-line">
                    <span className="timestamp">[{log.timestamp}]</span>
                    {log.type === 'system' ? (
                      <span className="prefix system-prefix">&lt;SYS&gt;</span>
                    ) : (
                      <span className="prefix rx-prefix">&lt;RX&gt;</span>
                    )}
                    {log.isBits ? (
                      <span className="bits">{log.message}</span>
                    ) : (
                      <span className="message">{log.message}</span>
                    )}
                  </div>
                ))}
              </div>

              {/* Live stream indicator bar */}
              <div className="live-bits-banner receiver">
                <div className="live-bits-title">Current Decoding:</div>
                <div className="live-bits-stream" style={{ color: 'var(--green)' }}>
                  {rxTelemetry.word ? `WORD: "${rxTelemetry.word}"` : 'AWAITING PREAMBLE'}
                </div>
              </div>
            </div>
          </section>
        </main>
      </div>

      {/* History Log Section */}
      <section className="card history-section">
        <div className="card-title">
          <History size={18} style={{ color: 'var(--cyan)' }} />
          Historical Transmission logs
        </div>
        
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Channel Unit</th>
                <th>Decoded Message</th>
                <th>Raw Bit stream</th>
                <th>Transfer Status</th>
              </tr>
            </thead>
            <tbody>
              {history.length === 0 ? (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '24px' }}>
                    No transmission history matches database records.
                  </td>
                </tr>
              ) : (
                history.map((row) => (
                  <tr key={row.id}>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
                      {new Date(row.timestamp).toLocaleString()}
                    </td>
                    <td>
                      <span className={`badge ${row.direction === 'SENT' ? 'badge-sent' : 'badge-received'}`}>
                        {row.direction === 'SENT' ? 'Transmitter' : 'Receiver'}
                      </span>
                    </td>
                    <td style={{ fontWeight: '500' }}>
                      "{row.text}"
                    </td>
                    <td>
                      <div className="binary-code-font" title={row.binary_data}>
                        {row.binary_data || 'N/A'}
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${
                        row.status === 'SUCCESS' ? 'badge-success' : 
                        row.status === 'FAILED' ? 'badge-failed' : 'badge-pending'
                      }`}>
                        {row.status === 'SUCCESS' && <CheckCircle size={10} style={{ marginRight: '4px' }} />}
                        {row.status === 'FAILED' && <XCircle size={10} style={{ marginRight: '4px' }} />}
                        {row.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export default App;
