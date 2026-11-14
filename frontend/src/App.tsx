import { useState, useEffect } from 'react';
import {
  Users,
  LayoutDashboard,
  CalendarRange,
  Plus,
  ShieldCheck,
  Clock,
  Calendar,
} from 'lucide-react';
import { DayBoard, type BookingPrefill } from './components/DayBoard';
import { WeekBoard } from './components/WeekBoard';
import { BookingModal } from './components/BookingModal';
import { DirectoryPage } from './components/DirectoryPage';
import { getTodayIso } from './utils/time';

type ActiveTab = 'board' | 'week' | 'directory';

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('board');
  const [selectedDate, setSelectedDate] = useState(() => getTodayIso());
  const [isBookingModalOpen, setIsBookingModalOpen] = useState(false);
  const [bookingPrefill, setBookingPrefill] = useState<BookingPrefill>({});
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [studioTime, setStudioTime] = useState('');

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setStudioTime(
        `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
      );
    };
    updateClock();
    const timer = setInterval(updateClock, 30000);
    return () => clearInterval(timer);
  }, []);

  const handleOpenBookingModal = (prefill?: BookingPrefill) => {
    setBookingPrefill(prefill || {});
    setIsBookingModalOpen(true);
  };

  const handleCloseBookingModal = () => {
    setIsBookingModalOpen(false);
    setBookingPrefill({});
  };

  const handleBookingSuccess = () => {
    setRefreshTrigger((k) => k + 1);
  };

  const handleSelectDayFromWeek = (date: string) => {
    setSelectedDate(date);
    setActiveTab('board');
  };

  const navItems: Array<{
    id: ActiveTab;
    label: string;
    subtitle: string;
    testId: string;
    icon: typeof LayoutDashboard;
  }> = [
    {
      id: 'board',
      label: 'Day Board',
      subtitle: 'Columns & Gantt timeline',
      testId: 'tab-board',
      icon: LayoutDashboard,
    },
    {
      id: 'week',
      label: 'Week Overview',
      subtitle: '7-day studio matrix',
      testId: 'tab-week',
      icon: CalendarRange,
    },
    {
      id: 'directory',
      label: 'Directory',
      subtitle: 'Specialists, clients, rooms',
      testId: 'tab-directory',
      icon: Users,
    },
  ];

  return (
    <div className="min-h-screen bg-slate-100/70 flex flex-col lg:flex-row font-sans text-slate-900">
      {/* Left Sidebar (Desktop & Persistent Navigation) */}
      <aside className="no-print w-full lg:w-72 lg:shrink-0 bg-slate-900 text-slate-100 flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-slate-800">
        <div className="p-5 space-y-6">
          {/* Brand Block */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500 flex items-center justify-center text-white font-bold text-lg shadow-md shadow-indigo-950/50">
              SB
            </div>
            <div>
              <h1 className="text-base font-bold text-white tracking-tight leading-tight">
                SessionBoard
              </h1>
              <p className="text-[11px] text-slate-400 font-medium">Studio Operations Suite</p>
            </div>
          </div>

          {/* Primary CTA */}
          <button
            type="button"
            onClick={() => handleOpenBookingModal({ date: selectedDate })}
            className="w-full flex items-center justify-center gap-2 bg-indigo-500 hover:bg-indigo-400 text-white py-2.5 px-4 rounded-xl text-sm font-semibold shadow-sm shadow-indigo-950/50 transition"
          >
            <Plus className="w-4 h-4" />
            Book Session
          </button>

          {/* Navigation Menu */}
          <nav data-testid="sidebar-nav" aria-label="Primary navigation" className="space-y-1.5">
            <div className="px-2.5 pb-1 text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Workspace
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  data-testid={item.testId}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition ${
                    isActive
                      ? 'bg-indigo-600/20 text-white border border-indigo-400/30 shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800/80 border border-transparent'
                  }`}
                >
                  <span
                    className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                      isActive
                        ? 'bg-indigo-500 text-white'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold leading-tight">{item.label}</div>
                    <div className="text-[11px] text-slate-400 truncate">{item.subtitle}</div>
                  </div>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Bottom Studio Status & Quick Date Jump */}
        <div className="p-5 pt-0 lg:pt-5 border-t border-slate-800/80 space-y-3 hidden lg:block">
          <div className="bg-slate-800/70 border border-slate-700/70 rounded-xl p-3.5 space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400 font-medium flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                Active Date
              </span>
              <button
                type="button"
                onClick={() => setSelectedDate(getTodayIso())}
                className="text-[11px] font-semibold text-indigo-300 hover:text-indigo-200"
              >
                Jump Today
              </button>
            </div>
            <input
              type="date"
              aria-label="Quick date jump"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="bg-slate-800/50 border border-slate-800 rounded-xl p-3.5 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                Studio Hours
              </span>
              <span className="font-mono font-semibold text-slate-200">08:00–20:00</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                Conflict Guard
              </span>
              <span className="inline-flex items-center gap-1.5 text-emerald-400 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                Active
              </span>
            </div>
            {studioTime && (
              <div className="pt-1.5 border-t border-slate-700/60 flex items-center justify-between text-[11px] text-slate-400">
                <span>Local Time</span>
                <span className="font-mono text-slate-200">{studioTime}</span>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Main Workspace */}
      <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 max-w-[1440px] w-full mx-auto">
        {activeTab === 'board' && (
          <DayBoard
            selectedDate={selectedDate}
            onDateChange={setSelectedDate}
            onOpenBookingModal={handleOpenBookingModal}
            refreshTrigger={refreshTrigger}
          />
        )}
        {activeTab === 'week' && (
          <WeekBoard
            selectedDate={selectedDate}
            onDateChange={setSelectedDate}
            onSelectDayView={handleSelectDayFromWeek}
            onOpenBookingModal={handleOpenBookingModal}
            refreshTrigger={refreshTrigger}
          />
        )}
        {activeTab === 'directory' && <DirectoryPage />}
      </main>

      {/* Booking Modal */}
      <BookingModal
        isOpen={isBookingModalOpen}
        onClose={handleCloseBookingModal}
        onSuccess={handleBookingSuccess}
        initialDate={bookingPrefill.date || selectedDate}
        initialRoomId={bookingPrefill.roomId}
        initialSpecialistId={bookingPrefill.specialistId}
        initialClientId={bookingPrefill.clientId}
        initialStartTime={bookingPrefill.startTime}
      />
    </div>
  );
}
