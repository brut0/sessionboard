import { useState } from 'react';
import { Calendar, Users, LayoutDashboard, Plus } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'board' | 'directory'>('board');
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().split('T')[0]);

  const handlePrevDay = () => {
    const d = new Date(selectedDate);
    d.setDate(d.getDate() - 1);
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  const handleNextDay = () => {
    const d = new Date(selectedDate);
    d.setDate(d.getDate() + 1);
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  const handleToday = () => {
    setSelectedDate(new Date().toISOString().split('T')[0]);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Top Navigation */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
            SB
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">SessionBoard</h1>
            <p className="text-xs text-slate-500">Studio Session Scheduler</p>
          </div>
        </div>

        <nav className="flex items-center gap-2 bg-slate-100 p-1 rounded-lg">
          <button
            type="button"
            data-testid="tab-board"
            onClick={() => setActiveTab('board')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition ${
              activeTab === 'board'
                ? 'bg-white text-indigo-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            Day Board
          </button>
          <button
            type="button"
            data-testid="tab-directory"
            onClick={() => setActiveTab('directory')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition ${
              activeTab === 'directory'
                ? 'bg-white text-indigo-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Users className="w-4 h-4" />
            Directory
          </button>
        </nav>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
        {activeTab === 'board' ? (
          <div className="space-y-6">
            {/* Board Controls */}
            <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  data-testid="btn-prev-day"
                  onClick={handlePrevDay}
                  className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
                >
                  ◀ Prev
                </button>
                <button
                  type="button"
                  data-testid="btn-today"
                  onClick={handleToday}
                  className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
                >
                  Today
                </button>
                <button
                  type="button"
                  data-testid="btn-next-day"
                  onClick={handleNextDay}
                  className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
                >
                  Next ▶
                </button>
                <div className="flex items-center gap-2 ml-2 pl-3 border-l border-slate-200">
                  <Calendar className="w-4 h-4 text-slate-400" />
                  <input
                    type="date"
                    data-testid="date-picker"
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    className="border border-slate-300 rounded-md px-2.5 py-1 text-sm text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <button
                type="button"
                data-testid="btn-new-session"
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium shadow-xs transition"
              >
                <Plus className="w-4 h-4" />
                New Session
              </button>
            </div>

            {/* Room Columns Placeholder */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {['Room A', 'Room B', 'Room C'].map((room) => (
                <div key={room} className="bg-white rounded-xl border border-slate-200 shadow-xs p-4 flex flex-col">
                  <h2 className="font-semibold text-slate-800 pb-3 border-b border-slate-100">{room}</h2>
                  <div className="py-12 text-center text-sm text-slate-400">No sessions scheduled</div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {['Specialists', 'Clients', 'Rooms'].map((section) => (
              <div key={section} className="bg-white rounded-xl border border-slate-200 shadow-xs p-5">
                <h2 className="font-bold text-slate-800 text-base mb-4">{section}</h2>
                <div className="py-8 text-center text-sm text-slate-400">Directory loaded</div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
