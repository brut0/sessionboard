import { useState } from 'react';
import { Users, LayoutDashboard } from 'lucide-react';
import { DayBoard } from './components/DayBoard';
import { BookingModal } from './components/BookingModal';
import { DirectoryPage } from './components/DirectoryPage';

export default function App() {
  const [activeTab, setActiveTab] = useState<'board' | 'directory'>('board');
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [isBookingModalOpen, setIsBookingModalOpen] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleBookingSuccess = () => {
    setRefreshTrigger((k) => k + 1);
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
          <DayBoard
            selectedDate={selectedDate}
            onDateChange={setSelectedDate}
            onOpenBookingModal={() => setIsBookingModalOpen(true)}
            refreshTrigger={refreshTrigger}
          />
        ) : (
          <DirectoryPage />
        )}
      </main>

      {/* Booking Modal */}
      <BookingModal
        isOpen={isBookingModalOpen}
        onClose={() => setIsBookingModalOpen(false)}
        onSuccess={handleBookingSuccess}
        initialDate={selectedDate}
      />
    </div>
  );
}
