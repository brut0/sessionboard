import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { UserCheck, Users, DoorOpen, Plus, Trash2, AlertCircle, Search } from 'lucide-react';
import {
  apiClient,
  type Specialist,
  type Client,
  type Room,
  type ErrorDetail,
} from '../api/client';
import { getSpecialtyTheme, getInitials } from '../utils/theme';

export const DirectoryPage: React.FC = () => {
  const [specialists, setSpecialists] = useState<Specialist[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Form states
  const [specName, setSpecName] = useState('');
  const [specSpecialty, setSpecSpecialty] = useState('');
  const [clientDisplayName, setClientDisplayName] = useState('');
  const [roomName, setRoomName] = useState('');

  // Error banners
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const fetchDirectory = useCallback(async () => {
    setLoading(true);
    try {
      const [specRes, clientRes, roomRes] = await Promise.all([
        apiClient.GET('/api/specialists'),
        apiClient.GET('/api/clients'),
        apiClient.GET('/api/rooms'),
      ]);

      if (specRes.data) setSpecialists(specRes.data);
      if (clientRes.data) setClients(clientRes.data);
      if (roomRes.data) setRooms(roomRes.data);
    } catch {
      setErrorBanner('Failed to load studio directory');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDirectory();
  }, [fetchDirectory]);

  // --- Specialist handlers ---
  const handleAddSpecialist = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorBanner(null);
    if (!specName.trim() || !specSpecialty.trim()) return;

    const { data, error } = await apiClient.POST('/api/specialists', {
      body: { name: specName.trim(), specialty: specSpecialty.trim() },
    });

    if (error) {
      setErrorBanner('Failed to create specialist');
      return;
    }

    if (data) {
      setSpecialists((prev) => [...prev, data].sort((a, b) => a.name.localeCompare(b.name)));
      setSpecName('');
      setSpecSpecialty('');
    }
  };

  const handleDeleteSpecialist = async (id: number) => {
    setErrorBanner(null);
    const { error, response } = await apiClient.DELETE('/api/specialists/{specialist_id}', {
      params: { path: { specialist_id: id } },
    });

    if (response.status === 409) {
      const detail = (error as ErrorDetail)?.detail;
      if (detail === 'has_planned_sessions') {
        setErrorBanner('Cannot delete: has planned sessions');
      } else {
        setErrorBanner('Cannot delete: referenced by sessions');
      }
      return;
    }

    if (response.status === 204) {
      setSpecialists((prev) => prev.filter((s) => s.id !== id));
    }
  };

  // --- Client handlers ---
  const handleAddClient = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorBanner(null);
    if (!clientDisplayName.trim()) return;

    const { data, error } = await apiClient.POST('/api/clients', {
      body: { display_name: clientDisplayName.trim() },
    });

    if (error) {
      setErrorBanner('Failed to create client');
      return;
    }

    if (data) {
      setClients((prev) =>
        [...prev, data].sort((a, b) => a.display_name.localeCompare(b.display_name))
      );
      setClientDisplayName('');
    }
  };

  const handleDeleteClient = async (id: number) => {
    setErrorBanner(null);
    const { error, response } = await apiClient.DELETE('/api/clients/{client_id}', {
      params: { path: { client_id: id } },
    });

    if (response.status === 409) {
      const detail = (error as ErrorDetail)?.detail;
      if (detail === 'has_planned_sessions') {
        setErrorBanner('Cannot delete: has planned sessions');
      } else {
        setErrorBanner('Cannot delete: referenced by sessions');
      }
      return;
    }

    if (response.status === 204) {
      setClients((prev) => prev.filter((c) => c.id !== id));
    }
  };

  // --- Room handlers ---
  const handleAddRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorBanner(null);
    if (!roomName.trim()) return;

    const { data, error, response } = await apiClient.POST('/api/rooms', {
      body: { name: roomName.trim() },
    });

    if (response.status === 409) {
      const detail = (error as ErrorDetail)?.detail;
      if (detail === 'room_name_taken') {
        setErrorBanner('Room name already exists');
      } else {
        setErrorBanner('Cannot add room: conflict');
      }
      return;
    }

    if (error) {
      setErrorBanner('Failed to create room');
      return;
    }

    if (data) {
      setRooms((prev) => [...prev, data].sort((a, b) => a.name.localeCompare(b.name)));
      setRoomName('');
    }
  };

  const handleDeleteRoom = async (id: number) => {
    setErrorBanner(null);
    const { error, response } = await apiClient.DELETE('/api/rooms/{room_id}', {
      params: { path: { room_id: id } },
    });

    if (response.status === 409) {
      const detail = (error as ErrorDetail)?.detail;
      if (detail === 'has_planned_sessions') {
        setErrorBanner('Cannot delete: has planned sessions');
      } else {
        setErrorBanner('Cannot delete: referenced by sessions');
      }
      return;
    }

    if (response.status === 204) {
      setRooms((prev) => prev.filter((r) => r.id !== id));
    }
  };

  const normalizedQuery = searchQuery.trim().toLowerCase();

  const filteredSpecialists = useMemo(
    () =>
      normalizedQuery
        ? specialists.filter(
            (s) =>
              s.name.toLowerCase().includes(normalizedQuery) ||
              s.specialty.toLowerCase().includes(normalizedQuery)
          )
        : specialists,
    [specialists, normalizedQuery]
  );

  const filteredClients = useMemo(
    () =>
      normalizedQuery
        ? clients.filter((c) => c.display_name.toLowerCase().includes(normalizedQuery))
        : clients,
    [clients, normalizedQuery]
  );

  const filteredRooms = useMemo(
    () =>
      normalizedQuery
        ? rooms.filter((r) => r.name.toLowerCase().includes(normalizedQuery))
        : rooms,
    [rooms, normalizedQuery]
  );

  return (
    <div data-testid="directory-page" className="space-y-5">
      {/* Page Title & Search Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">Studio Directory</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage specialists, clients, and studio rooms available for scheduling.
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
          <input
            type="search"
            data-testid="directory-search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter specialists, clients, rooms..."
            className="w-full border border-slate-300 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-800 bg-slate-50 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500 transition"
          />
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
              Active Specialists
            </span>
            <span className="text-xl font-bold text-slate-900 font-mono tabular-nums mt-0.5 block">
              {specialists.length}
            </span>
          </div>
          <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <UserCheck className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
              Registered Clients
            </span>
            <span className="text-xl font-bold text-slate-900 font-mono tabular-nums mt-0.5 block">
              {clients.length}
            </span>
          </div>
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Users className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/90 p-3.5 shadow-2xs flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
              Studio Rooms
            </span>
            <span className="text-xl font-bold text-slate-900 font-mono tabular-nums mt-0.5 block">
              {rooms.length}
            </span>
          </div>
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <DoorOpen className="w-5 h-5" />
          </div>
        </div>
      </div>

      {errorBanner && (
        <div
          data-testid="directory-error-banner"
          className="p-3.5 bg-red-50 border border-red-200 text-red-800 rounded-xl text-sm flex items-center justify-between shadow-2xs"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
            <span>{errorBanner}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorBanner(null)}
            className="text-xs font-semibold text-red-600 hover:text-red-900 px-2 py-0.5 rounded hover:bg-red-100 transition"
          >
            Dismiss
          </button>
        </div>
      )}

      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200 py-12 text-center text-sm text-slate-400">
          Loading directory...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Specialists Card */}
          <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-5 flex flex-col">
            <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-100">
              <UserCheck className="w-5 h-5 text-indigo-600" />
              <h3 className="font-bold text-slate-800 text-base">Specialists</h3>
              <span className="ml-auto text-xs font-medium px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full font-mono">
                {filteredSpecialists.length}
              </span>
            </div>

            {/* List */}
            <ul data-testid="specialist-list" className="space-y-2 flex-1 mb-4 overflow-y-auto max-h-80">
              {filteredSpecialists.length === 0 ? (
                <li className="py-6 text-center text-xs text-slate-400 italic">
                  {specialists.length === 0 ? 'No specialists registered' : 'No matching specialists'}
                </li>
              ) : (
                filteredSpecialists.map((s) => {
                  const theme = getSpecialtyTheme(s.name);
                  return (
                    <li
                      key={s.id}
                      className="flex items-center justify-between p-2.5 rounded-xl border border-slate-100 bg-slate-50/50 hover:bg-slate-50 transition gap-2"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span
                          className={`w-8 h-8 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ${theme.avatarBg} ${theme.avatarText}`}
                        >
                          {getInitials(s.name)}
                        </span>
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-slate-900 truncate">
                            {s.name}
                          </div>
                          <span
                            className={`inline-block mt-0.5 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${theme.bgBadge} ${theme.textBadge} ${theme.borderBadge}`}
                          >
                            {s.specialty}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        data-testid={`btn-delete-specialist-${s.id}`}
                        onClick={() => handleDeleteSpecialist(s.id)}
                        className="p-1.5 text-slate-400 hover:text-red-600 rounded-md hover:bg-red-50 transition shrink-0"
                        title="Delete specialist"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </li>
                  );
                })
              )}
            </ul>

            {/* Add Specialist Form */}
            <form onSubmit={handleAddSpecialist} className="pt-3 border-t border-slate-100 space-y-2">
              <input
                type="text"
                data-testid="input-specialist-name"
                placeholder="Full name"
                value={specName}
                onChange={(e) => setSpecName(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                required
              />
              <input
                type="text"
                data-testid="input-specialist-specialty"
                placeholder="Specialty (e.g. Math tutor)"
                value={specSpecialty}
                onChange={(e) => setSpecSpecialty(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                required
              />
              <button
                type="submit"
                data-testid="btn-add-specialist"
                className="w-full flex items-center justify-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium py-2 rounded-lg shadow-2xs transition"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Specialist
              </button>
            </form>
          </div>

          {/* Clients Card */}
          <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-5 flex flex-col">
            <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-100">
              <Users className="w-5 h-5 text-indigo-600" />
              <h3 className="font-bold text-slate-800 text-base">Clients</h3>
              <span className="ml-auto text-xs font-medium px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full font-mono">
                {filteredClients.length}
              </span>
            </div>

            {/* List */}
            <ul data-testid="client-list" className="space-y-2 flex-1 mb-4 overflow-y-auto max-h-80">
              {filteredClients.length === 0 ? (
                <li className="py-6 text-center text-xs text-slate-400 italic">
                  {clients.length === 0 ? 'No clients registered' : 'No matching clients'}
                </li>
              ) : (
                filteredClients.map((c) => (
                  <li
                    key={c.id}
                    className="flex items-center justify-between p-2.5 rounded-xl border border-slate-100 bg-slate-50/50 hover:bg-slate-50 transition gap-2"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="w-8 h-8 rounded-full bg-slate-200/80 text-slate-700 text-xs font-bold flex items-center justify-center shrink-0">
                        {getInitials(c.display_name)}
                      </span>
                      <div className="text-sm font-semibold text-slate-900 truncate">
                        {c.display_name}
                      </div>
                    </div>
                    <button
                      type="button"
                      data-testid={`btn-delete-client-${c.id}`}
                      onClick={() => handleDeleteClient(c.id)}
                      className="p-1.5 text-slate-400 hover:text-red-600 rounded-md hover:bg-red-50 transition shrink-0"
                      title="Delete client"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </li>
                ))
              )}
            </ul>

            {/* Add Client Form */}
            <form onSubmit={handleAddClient} className="pt-3 border-t border-slate-100 space-y-2">
              <input
                type="text"
                data-testid="input-client-name"
                placeholder="Client display name (e.g. Client 01)"
                value={clientDisplayName}
                onChange={(e) => setClientDisplayName(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                required
              />
              <button
                type="submit"
                data-testid="btn-add-client"
                className="w-full flex items-center justify-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium py-2 rounded-lg shadow-2xs transition"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Client
              </button>
            </form>
          </div>

          {/* Rooms Card */}
          <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-5 flex flex-col">
            <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-100">
              <DoorOpen className="w-5 h-5 text-indigo-600" />
              <h3 className="font-bold text-slate-800 text-base">Rooms</h3>
              <span className="ml-auto text-xs font-medium px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full font-mono">
                {filteredRooms.length}
              </span>
            </div>

            {/* List */}
            <ul data-testid="room-list" className="space-y-2 flex-1 mb-4 overflow-y-auto max-h-80">
              {filteredRooms.length === 0 ? (
                <li className="py-6 text-center text-xs text-slate-400 italic">
                  {rooms.length === 0 ? 'No rooms registered' : 'No matching rooms'}
                </li>
              ) : (
                filteredRooms.map((r) => (
                  <li
                    key={r.id}
                    className="flex items-center justify-between p-2.5 rounded-xl border border-slate-100 bg-slate-50/50 hover:bg-slate-50 transition gap-2"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                        <DoorOpen className="w-4 h-4" />
                      </span>
                      <div className="text-sm font-semibold text-slate-900 truncate">{r.name}</div>
                    </div>
                    <button
                      type="button"
                      data-testid={`btn-delete-room-${r.id}`}
                      onClick={() => handleDeleteRoom(r.id)}
                      className="p-1.5 text-slate-400 hover:text-red-600 rounded-md hover:bg-red-50 transition shrink-0"
                      title="Delete room"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </li>
                ))
              )}
            </ul>

            {/* Add Room Form */}
            <form onSubmit={handleAddRoom} className="pt-3 border-t border-slate-100 space-y-2">
              <input
                type="text"
                data-testid="input-room-name"
                placeholder="Room name (e.g. Room D)"
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                required
              />
              <button
                type="submit"
                data-testid="btn-add-room"
                className="w-full flex items-center justify-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium py-2 rounded-lg shadow-2xs transition"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Room
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
