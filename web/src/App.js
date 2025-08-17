import React, { useState, useEffect } from 'react';
import './index.css';

function App() {
  const [requests, setRequests] = useState([]);
  const [stats, setStats] = useState({ total: 0, success: 0, failed: 0 });
  const [expandedRequest, setExpandedRequest] = useState(null);

  useEffect(() => {
    // Initial load
    const fetchInitialLogs = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/logs');
        const data = await response.json();
        const logs = data.logs;
        
        setRequests(logs.slice(-10).reverse());
        
        const total = logs.length;
        const success = logs.filter(log => log.status_code === 200).length;
        setStats({ total, success, failed: total - success });
      } catch (error) {
        console.error('Failed to fetch initial logs:', error);
      }
    };

    fetchInitialLogs();

    // WebSocket connection
    const ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'new_request') {
        const newRequest = message.data;
        setRequests(prev => [newRequest, ...prev].slice(0, 10));
        setStats(prev => ({
          total: prev.total + 1,
          success: prev.success + (newRequest.status_code === 200 ? 1 : 0),
          failed: prev.failed + (newRequest.status_code !== 200 ? 1 : 0)
        }));
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  return (
    <div className="max-w-6xl mx-auto p-6 bg-gray-50 min-h-screen">
      <header className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-800">🚀 HackRx System Monitor</h1>
      </header>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-blue-500">
          <h3 className="text-sm text-gray-600 mb-2">Total Requests</h3>
          <span className="text-2xl font-bold text-gray-800">{stats.total}</span>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-green-500">
          <h3 className="text-sm text-gray-600 mb-2">Success</h3>
          <span className="text-2xl font-bold text-gray-800">{stats.success}</span>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-red-500">
          <h3 className="text-sm text-gray-600 mb-2">Failed</h3>
          <span className="text-2xl font-bold text-gray-800">{stats.failed}</span>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-bold text-gray-800 mb-4">Recent Requests</h2>
        <div className="space-y-4">
          {requests.map((req, index) => (
            <div key={index} className={`border rounded-lg p-4 cursor-pointer transition-all ${
              req.status_code === 200 ? 'border-l-4 border-l-green-500 bg-green-50 hover:bg-green-100' : 'border-l-4 border-l-red-500 bg-red-50 hover:bg-red-100'
            }`} onClick={() => setExpandedRequest(expandedRequest === index ? null : index)}>
              <div className="flex justify-between items-center mb-3">
                <span className="text-sm text-gray-600">{new Date(req.timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}</span>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-1 rounded text-xs font-bold ${
                    req.status_code === 200 ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'
                  }`}>
                    {req.status_code}
                  </span>
                  <span className="text-xs text-gray-500">
                    {expandedRequest === index ? '▼' : '▶'}
                  </span>
                </div>
              </div>
              <div className="text-sm text-gray-700 space-y-1">
                <p><span className="font-semibold">Method:</span> {req.method}</p>
                <p><span className="font-semibold">Response Time:</span> {req.response_time_ms}ms</p>
                {req.body && (
                  <div className="mt-2 p-2 bg-gray-100 rounded">
                    <span className="font-semibold">Questions:</span> {JSON.parse(req.body).questions?.length || 0}
                  </div>
                )}
              </div>
              
              {expandedRequest === index && (
                <div className="mt-4 pt-4 border-t border-gray-200 space-y-4">
                  <div>
                    <h4 className="font-semibold text-gray-800 mb-2">Request Details</h4>
                    <div className="bg-white p-3 rounded border text-xs">
                      <p><span className="font-semibold">URL:</span> {req.url}</p>
                      <p><span className="font-semibold">Client IP:</span> {req.client_ip}</p>
                    </div>
                  </div>
                  
                  {req.headers && (
                    <div>
                      <h4 className="font-semibold text-gray-800 mb-2">Headers</h4>
                      <div className="bg-white p-3 rounded border text-xs max-h-32 overflow-y-auto">
                        {Object.entries(req.headers).map(([key, value]) => (
                          <p key={key}><span className="font-semibold">{key}:</span> {value}</p>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {req.body && (
                    <div>
                      <h4 className="font-semibold text-gray-800 mb-2">Request Body</h4>
                      <div className="bg-white p-3 rounded border text-xs max-h-40 overflow-y-auto">
                        <pre className="whitespace-pre-wrap">{req.body}</pre>
                      </div>
                    </div>
                  )}
                  
                  {req.response_body && (
                    <div>
                      <h4 className="font-semibold text-gray-800 mb-2">Response Body</h4>
                      <div className="bg-white p-3 rounded border text-xs max-h-40 overflow-y-auto">
                        <pre className="whitespace-pre-wrap">{JSON.stringify(JSON.parse(req.response_body), null, 2)}</pre>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;