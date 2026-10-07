import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Avatar,
  Box,
  Button,
  ButtonBase,
  Card,
  Chip,
  Grid,
  IconButton,
  Skeleton,
  Tooltip,
  Typography,
} from '@mui/material';
import PeopleIcon from '@mui/icons-material/People';
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber';
import DevicesIcon from '@mui/icons-material/Devices';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import DonutLargeIcon from '@mui/icons-material/DonutLarge';
import KeyIcon from '@mui/icons-material/VpnKey';
import AddIcon from '@mui/icons-material/Add';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import RefreshIcon from '@mui/icons-material/Refresh';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import HourglassTopIcon from '@mui/icons-material/HourglassTop';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import api from '../../api/axios';
import { useAuth } from '../../context/AuthContext';

const C = {
  primary: '#4F46E5',
  violet: '#7C3AED',
  sky: '#0EA5E9',
  green: '#10B981',
  amber: '#F59E0B',
  orange: '#F97316',
  red: '#EF4444',
  slate: '#94A3B8',
  grid: '#F1F5F9',
  axis: '#94A3B8',
};

const PRIORITY_META = {
  critical: { label: 'Critical', color: '#DC2626' },
  high: { label: 'High', color: C.orange },
  medium: { label: 'Medium', color: C.amber },
  low: { label: 'Low', color: C.slate },
};

const TICKET_STATUS_META = {
  open: { label: 'Open', color: C.red },
  in_progress: { label: 'In progress', color: C.amber },
  resolved: { label: 'Resolved', color: C.green },
  closed: { label: 'Closed', color: C.slate },
};

const ASSET_STATUS_META = {
  assigned: { label: 'Assigned', color: C.primary },
  available: { label: 'Available', color: C.green },
  maintenance: { label: 'Maintenance', color: C.amber },
  retired: { label: 'Retired', color: '#CBD5E1' },
};

const CHART_PALETTE = [C.primary, C.sky, C.green, C.amber, C.violet, C.red, '#EC4899', '#14B8A6'];

const INTEGRATION_LINKS = {
  suremdm: '/integrations?tab=suremdm',
  trellix: '/integrations?tab=trellix',
  teamviewer: '/integrations?tab=teamviewer',
  synthesia: '/integrations?tab=synthesia',
  dell: '/integrations?tab=dell',
  google_workspace: '/google-workspace',
};

// ---------- helpers ----------

const fmt = (n) => (n === null || n === undefined ? '--' : Number(n).toLocaleString());

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

function timeAgo(value) {
  if (!value) return '';
  const diff = (Date.now() - new Date(value).getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

function shortDate(value) {
  if (!value) return '';
  return new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

function daysUntil(value) {
  if (!value) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((new Date(`${value}T00:00:00`) - today) / 86400000);
}

function initials(name = '') {
  return name.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('') || '?';
}

// ---------- building blocks ----------

function SectionCard({ title, subtitle, action, onAction, children, sx }) {
  return (
    <Card sx={{ p: 2.5, height: '100%', display: 'flex', flexDirection: 'column', ...sx }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1, mb: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontWeight: 700, fontSize: 15 }}>{title}</Typography>
          {subtitle && (
            <Typography color="text.secondary" sx={{ fontSize: 12.5, mt: 0.25 }}>{subtitle}</Typography>
          )}
        </Box>
        {action && (
          <Button size="small" endIcon={<ArrowForwardIcon sx={{ fontSize: 16 }} />} onClick={onAction} sx={{ flexShrink: 0, px: 1 }}>
            {action}
          </Button>
        )}
      </Box>
      <Box sx={{ flex: 1, minHeight: 0 }}>{children}</Box>
    </Card>
  );
}

function EmptyState({ icon, text, height = 160 }) {
  return (
    <Box sx={{ height, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 1, color: 'text.secondary' }}>
      {icon && React.cloneElement(icon, { sx: { fontSize: 30, color: '#CBD5E1' } })}
      <Typography sx={{ fontSize: 13 }}>{text}</Typography>
    </Box>
  );
}

function KpiTile({ label, value, sub, icon, color, onClick, loading }) {
  return (
    <Card
      component={onClick ? ButtonBase : 'div'}
      onClick={onClick}
      sx={{
        width: '100%',
        height: '100%',
        display: 'block',
        textAlign: 'left',
        p: 2,
        transition: 'border-color .15s, box-shadow .15s',
        ...(onClick && { '&:hover': { borderColor: color, boxShadow: `0 4px 14px ${color}22` } }),
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.25 }}>
        <Box sx={{ width: 30, height: 30, borderRadius: '8px', bgcolor: `${color}14`, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
          {React.cloneElement(icon, { sx: { fontSize: 18, color } })}
        </Box>
        <Typography color="text.secondary" sx={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.2 }}>{label}</Typography>
      </Box>
      {loading ? (
        <>
          <Skeleton width={64} height={36} />
          <Skeleton width="80%" height={18} />
        </>
      ) : (
        <>
          <Typography sx={{ fontSize: 28, fontWeight: 800, lineHeight: 1.1, letterSpacing: '-0.02em' }}>{value}</Typography>
          <Typography color="text.secondary" sx={{ fontSize: 12, mt: 0.5, minHeight: 18 }} noWrap>{sub}</Typography>
        </>
      )}
    </Card>
  );
}

function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <Box sx={{ bgcolor: '#0F172A', borderRadius: '8px', px: 1.5, py: 1, boxShadow: '0 10px 25px rgba(0,0,0,0.25)' }}>
      {label !== undefined && <Typography sx={{ color: '#94A3B8', fontSize: 11, mb: 0.5 }}>{label}</Typography>}
      {payload.map((p) => (
        <Box key={p.dataKey || p.name} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ width: 8, height: 8, borderRadius: '2px', bgcolor: p.color || p.payload?.fill }} />
          <Typography sx={{ color: '#E2E8F0', fontSize: 12 }}>{p.name}</Typography>
          <Typography sx={{ color: '#F8FAFC', fontSize: 12, fontWeight: 700, ml: 'auto', pl: 1.5 }}>{fmt(p.value)}</Typography>
        </Box>
      ))}
    </Box>
  );
}

function MeterRow({ label, value, total, color, right }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <Box sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: color, mr: 1 }} />
        <Typography sx={{ fontSize: 13, fontWeight: 500 }}>{label}</Typography>
        <Typography sx={{ fontSize: 13, fontWeight: 700, ml: 'auto' }}>{right ?? fmt(value)}</Typography>
      </Box>
      <Box sx={{ height: 6, borderRadius: 3, bgcolor: C.grid, overflow: 'hidden' }}>
        <Box sx={{ width: `${pct}%`, height: '100%', bgcolor: color, borderRadius: 3, transition: 'width .4s' }} />
      </Box>
    </Box>
  );
}

function SegmentBar({ segments, height = 10 }) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  return (
    <Box sx={{ display: 'flex', height, borderRadius: height / 2, overflow: 'hidden', bgcolor: C.grid, gap: '2px' }}>
      {total > 0 && segments.filter((s) => s.value > 0).map((s) => (
        <Tooltip key={s.label} title={`${s.label}: ${s.value}`} arrow>
          <Box sx={{ flex: s.value, bgcolor: s.color }} />
        </Tooltip>
      ))}
    </Box>
  );
}

function ListRow({ children, onClick, last }) {
  return (
    <Box
      onClick={onClick}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        py: 1.1,
        px: 1,
        mx: -1,
        borderRadius: '8px',
        borderBottom: last ? 'none' : '1px solid #F1F5F9',
        cursor: onClick ? 'pointer' : 'default',
        '&:hover': onClick ? { bgcolor: '#F8FAFC' } : undefined,
      }}
    >
      {children}
    </Box>
  );
}

function StatusDot({ status }) {
  const color = status === 'success' ? C.green : status === 'failed' ? C.red : status === 'idle' ? '#CBD5E1' : C.amber;
  return (
    <Box sx={{ position: 'relative', width: 10, height: 10, flexShrink: 0 }}>
      <Box sx={{ position: 'absolute', inset: 0, borderRadius: '50%', bgcolor: color }} />
      {status === 'success' && (
        <Box sx={{ position: 'absolute', inset: -3, borderRadius: '50%', bgcolor: `${color}33` }} />
      )}
    </Box>
  );
}

// ---------- sections ----------

function TicketTrendCard({ tickets, loading, onOpen }) {
  const data = (tickets?.trend || []).map((d) => ({ ...d, label: shortDate(d.date) }));
  const created = data.reduce((s, d) => s + d.created, 0);
  const resolved = data.reduce((s, d) => s + d.resolved, 0);
  return (
    <SectionCard
      title="Ticket activity"
      subtitle="Raised vs resolved, last 14 days"
      action="All tickets"
      onAction={onOpen}
    >
      <Box sx={{ display: 'flex', gap: 3, mb: 1.5 }}>
        {[
          { label: 'Raised', value: created, color: C.primary },
          { label: 'Resolved', value: resolved, color: C.green },
          { label: 'Active now', value: tickets?.active, color: C.red },
        ].map((m) => (
          <Box key={m.label}>
            <Typography color="text.secondary" sx={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Box component="span" sx={{ width: 8, height: 8, borderRadius: '2px', bgcolor: m.color }} />
              {m.label}
            </Typography>
            {loading ? <Skeleton width={30} height={28} /> : (
              <Typography sx={{ fontSize: 20, fontWeight: 800 }}>{fmt(m.value)}</Typography>
            )}
          </Box>
        ))}
      </Box>
      {loading ? (
        <Skeleton variant="rectangular" height={210} sx={{ borderRadius: 2 }} />
      ) : (
        <ResponsiveContainer width="100%" height={210}>
          <AreaChart data={data} margin={{ top: 5, right: 8, left: -24, bottom: 0 }}>
            <defs>
              <linearGradient id="gradCreated" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={C.primary} stopOpacity={0.25} />
                <stop offset="100%" stopColor={C.primary} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradResolved" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={C.green} stopOpacity={0.2} />
                <stop offset="100%" stopColor={C.green} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: C.axis }} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={16} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: C.axis }} axisLine={false} tickLine={false} domain={[0, (max) => Math.max(4, max)]} />
            <ChartTooltip content={<ChartTip />} />
            <Area type="monotone" dataKey="created" name="Raised" stroke={C.primary} strokeWidth={2} fill="url(#gradCreated)" />
            <Area type="monotone" dataKey="resolved" name="Resolved" stroke={C.green} strokeWidth={2} fill="url(#gradResolved)" />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </SectionCard>
  );
}

function TicketBreakdownCard({ tickets, loading, onOpen }) {
  const active = tickets?.active || 0;
  const status = tickets?.status_counts || {};
  return (
    <SectionCard title="Ticket queue" subtitle="Active tickets by priority" action="Open" onAction={onOpen}>
      {loading ? (
        <Skeleton variant="rectangular" height={240} sx={{ borderRadius: 2 }} />
      ) : (
        <>
          {Object.entries(PRIORITY_META).map(([key, meta]) => (
            <MeterRow key={key} label={meta.label} value={tickets?.priority_counts?.[key] || 0} total={active} color={meta.color} />
          ))}
          <Box sx={{ borderTop: '1px solid #F1F5F9', mt: 2, pt: 2 }}>
            <Typography color="text.secondary" sx={{ fontSize: 12, fontWeight: 600, mb: 1 }}>By status (all time)</Typography>
            <SegmentBar segments={Object.entries(TICKET_STATUS_META).map(([k, m]) => ({ label: m.label, value: status[k] || 0, color: m.color }))} />
            <Box sx={{ display: 'flex', flexWrap: 'wrap', columnGap: 2, rowGap: 0.5, mt: 1 }}>
              {Object.entries(TICKET_STATUS_META).map(([k, m]) => (
                <Typography key={k} sx={{ fontSize: 12, color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.75 }}>
                  <Box component="span" sx={{ width: 8, height: 8, borderRadius: '2px', bgcolor: m.color }} />
                  {m.label} <b style={{ color: '#0F172A' }}>{status[k] || 0}</b>
                </Typography>
              ))}
            </Box>
            {tickets?.unassigned > 0 && (
              <Alert severity="warning" sx={{ mt: 2, py: 0, fontSize: 12.5 }}>
                {tickets.unassigned} active ticket{tickets.unassigned === 1 ? '' : 's'} not assigned yet
              </Alert>
            )}
          </Box>
        </>
      )}
    </SectionCard>
  );
}

function InventoryByTypeCard({ inventory, loading, onOpen }) {
  const data = (inventory?.by_type || []).slice(0, 8).map((t) => ({
    name: t.name,
    Assigned: t.assigned,
    Available: t.available,
    Other: Math.max(0, t.count - t.assigned - t.available),
  }));
  return (
    <SectionCard title="Inventory by asset type" subtitle="Assigned vs in-stock across portal assets" action="IT assets" onAction={onOpen}>
      {loading ? (
        <Skeleton variant="rectangular" height={300} sx={{ borderRadius: 2 }} />
      ) : data.length === 0 ? (
        <EmptyState icon={<DevicesIcon />} text="No assets recorded yet." height={300} />
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(220, data.length * 36 + 40)}>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 12, left: 0, bottom: 0 }} barSize={16}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.grid} horizontal={false} />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: C.axis }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12, fill: '#475569' }} axisLine={false} tickLine={false} />
            <ChartTooltip content={<ChartTip />} cursor={{ fill: 'rgba(79,70,229,0.04)' }} />
            <Legend iconType="square" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="Assigned" stackId="a" fill={C.primary} />
            <Bar dataKey="Available" stackId="a" fill={C.green} />
            <Bar dataKey="Other" stackId="a" fill="#CBD5E1" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </SectionCard>
  );
}

function AssetHealthCard({ inventory, loading, onOpenAsset }) {
  const status = inventory?.status_counts || {};
  const pie = Object.entries(ASSET_STATUS_META).map(([k, m]) => ({ name: m.label, value: status[k] || 0, color: m.color }));
  const w = inventory?.warranty || {};
  const tracked = (w.expired || 0) + (w.next_30 || 0) + (w.next_90 || 0) + (w.covered || 0);
  return (
    <SectionCard title="Asset health" subtitle="Lifecycle status and warranty coverage">
      {loading ? (
        <Skeleton variant="rectangular" height={300} sx={{ borderRadius: 2 }} />
      ) : (
        <>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Box sx={{ position: 'relative', width: 140, height: 140, flexShrink: 0 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pie} dataKey="value" innerRadius={48} outerRadius={66} paddingAngle={2} stroke="none">
                    {pie.map((p) => <Cell key={p.name} fill={p.color} />)}
                  </Pie>
                  <ChartTooltip content={<ChartTip />} />
                </PieChart>
              </ResponsiveContainer>
              <Box sx={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', pointerEvents: 'none' }}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography sx={{ fontSize: 22, fontWeight: 800, lineHeight: 1 }}>{fmt(inventory?.total)}</Typography>
                  <Typography color="text.secondary" sx={{ fontSize: 11 }}>assets</Typography>
                </Box>
              </Box>
            </Box>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              {pie.map((p) => (
                <Box key={p.name} sx={{ display: 'flex', alignItems: 'center', py: 0.5 }}>
                  <Box sx={{ width: 8, height: 8, borderRadius: '2px', bgcolor: p.color, mr: 1 }} />
                  <Typography sx={{ fontSize: 13 }}>{p.name}</Typography>
                  <Typography sx={{ fontSize: 13, fontWeight: 700, ml: 'auto' }}>{fmt(p.value)}</Typography>
                </Box>
              ))}
            </Box>
          </Box>

          <Box sx={{ borderTop: '1px solid #F1F5F9', mt: 2, pt: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'baseline', mb: 1 }}>
              <Typography sx={{ fontSize: 13, fontWeight: 600 }}>Warranty</Typography>
              <Typography color="text.secondary" sx={{ fontSize: 12, ml: 'auto' }}>
                {tracked} tracked · {fmt(w.unknown)} without data
              </Typography>
            </Box>
            <SegmentBar
              segments={[
                { label: 'Expired', value: w.expired || 0, color: C.red },
                { label: 'Expires ≤ 30 days', value: w.next_30 || 0, color: C.orange },
                { label: 'Expires ≤ 90 days', value: w.next_90 || 0, color: C.amber },
                { label: 'Covered', value: w.covered || 0, color: C.green },
              ]}
            />
            <Box sx={{ display: 'flex', flexWrap: 'wrap', columnGap: 2, rowGap: 0.5, mt: 1 }}>
              {[['Expired', w.expired, C.red], ['≤ 30d', w.next_30, C.orange], ['≤ 90d', w.next_90, C.amber], ['Covered', w.covered, C.green]].map(([l, v, c]) => (
                <Typography key={l} sx={{ fontSize: 12, color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.75 }}>
                  <Box component="span" sx={{ width: 8, height: 8, borderRadius: '2px', bgcolor: c }} />
                  {l} <b style={{ color: '#0F172A' }}>{v || 0}</b>
                </Typography>
              ))}
            </Box>
            {(inventory?.expiring_soon || []).slice(0, 3).map((a, i, arr) => (
              <ListRow key={a.id} onClick={() => onOpenAsset(a.id)} last={i === arr.length - 1}>
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Typography sx={{ fontSize: 13, fontWeight: 600 }} noWrap>{a.asset_id}</Typography>
                  <Typography color="text.secondary" sx={{ fontSize: 12 }} noWrap>{a.asset_type}</Typography>
                </Box>
                <Chip
                  size="small"
                  label={a.days_left < 0 ? `Expired ${shortDate(a.warranty_expiry)}` : `${a.days_left}d left`}
                  sx={{ fontSize: 11, height: 22, fontWeight: 600, bgcolor: a.days_left < 0 ? '#FEE2E2' : '#FEF3C7', color: a.days_left < 0 ? '#991B1B' : '#92400E' }}
                />
              </ListRow>
            ))}
          </Box>
        </>
      )}
    </SectionCard>
  );
}

function useLiveSummary(url, enabled) {
  const [state, setState] = useState({ loading: enabled, data: null, error: '' });
  useEffect(() => {
    if (!enabled) {
      setState({ loading: false, data: null, error: '' });
      return undefined;
    }
    let cancelled = false;
    setState({ loading: true, data: null, error: '' });
    api.get(url)
      .then((res) => !cancelled && setState({ loading: false, data: res.data, error: '' }))
      .catch((err) => !cancelled && setState({ loading: false, data: null, error: err.response?.data?.detail || 'Could not reach the service.' }));
    return () => { cancelled = true; };
  }, [url, enabled]);
  return state;
}

function LiveCardBody({ enabled, state, notConfiguredText, children }) {
  if (!enabled) return <EmptyState text={notConfiguredText} height={150} />;
  if (state.loading) return <Skeleton variant="rectangular" height={150} sx={{ borderRadius: 2 }} />;
  if (state.error) return <Alert severity="warning" sx={{ fontSize: 12.5 }}>{state.error}</Alert>;
  return children;
}

function MdmCard({ enabled, onOpen }) {
  const state = useLiveSummary('/integrations/suremdm/summary/', enabled);
  const cats = (state.data?.categories || []).slice().sort((a, b) => b.count - a.count);
  const total = state.data?.total_systems || 0;
  return (
    <SectionCard title="Managed devices" subtitle="Live from SureMDM" action="MDM" onAction={onOpen}>
      <LiveCardBody enabled={enabled} state={state} notConfiguredText="SureMDM is not connected.">
        <Typography sx={{ fontSize: 28, fontWeight: 800, lineHeight: 1 }}>{fmt(total)}</Typography>
        <Typography color="text.secondary" sx={{ fontSize: 12, mb: 2 }}>enrolled systems</Typography>
        {cats.slice(0, 4).map((c, i) => (
          <MeterRow key={c.category} label={c.category || 'Uncategorised'} value={c.count} total={total} color={CHART_PALETTE[i % CHART_PALETTE.length]} />
        ))}
      </LiveCardBody>
    </SectionCard>
  );
}

function RemoteAccessCard({ enabled, onOpen }) {
  const state = useLiveSummary('/integrations/teamviewer/summary/', enabled);
  const states = state.data?.online_states || [];
  const total = state.data?.total_devices || 0;
  const online = states.filter((s) => String(s.online_state).toLowerCase() === 'online').reduce((a, s) => a + s.count, 0);
  return (
    <SectionCard title="Remote access" subtitle="Live from TeamViewer" action="Devices" onAction={onOpen}>
      <LiveCardBody enabled={enabled} state={state} notConfiguredText="TeamViewer is not connected.">
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
          <Typography sx={{ fontSize: 28, fontWeight: 800, lineHeight: 1, color: C.green }}>{fmt(online)}</Typography>
          <Typography color="text.secondary" sx={{ fontSize: 14, fontWeight: 600 }}>/ {fmt(total)}</Typography>
        </Box>
        <Typography color="text.secondary" sx={{ fontSize: 12, mb: 2 }}>devices online right now</Typography>
        <SegmentBar
          segments={states.map((s) => ({
            label: s.online_state,
            value: s.count,
            color: String(s.online_state).toLowerCase() === 'online' ? C.green : '#CBD5E1',
          }))}
        />
        <Box sx={{ mt: 1.5 }}>
          {states.map((s) => (
            <Box key={s.online_state} sx={{ display: 'flex', py: 0.4 }}>
              <Typography sx={{ fontSize: 13, textTransform: 'capitalize' }}>{s.online_state}</Typography>
              <Typography sx={{ fontSize: 13, fontWeight: 700, ml: 'auto' }}>{fmt(s.count)}</Typography>
            </Box>
          ))}
        </Box>
      </LiveCardBody>
    </SectionCard>
  );
}

function LicensesCard({ inventory, synthesiaEnabled, loading, onOpenInventory, onOpenSynthesia }) {
  const state = useLiveSummary('/integrations/synthesia/summary/', synthesiaEnabled);
  const lic = inventory?.licenses || {};
  const s = state.data;
  const allowance = s?.credit_allowance;
  const used = s?.credits_used_this_cycle;
  return (
    <SectionCard title="Licences & subscriptions" subtitle="Seat and credit consumption" action="Inventory" onAction={onOpenInventory}>
      {loading ? <Skeleton variant="rectangular" height={150} sx={{ borderRadius: 2 }} /> : (
        <>
          <MeterRow
            label={`Software seats · ${fmt(lic.total)} licence${lic.total === 1 ? '' : 's'}`}
            value={lic.used_seats || 0}
            total={lic.total_seats || 0}
            color={C.primary}
            right={`${fmt(lic.used_seats)} / ${fmt(lic.total_seats)}`}
          />
          {lic.unlimited > 0 && (
            <Typography color="text.secondary" sx={{ fontSize: 12, mt: -0.75, mb: 1.5 }}>
              + {lic.unlimited} unlimited-seat licence{lic.unlimited === 1 ? '' : 's'}
            </Typography>
          )}
          {synthesiaEnabled && (
            <Box sx={{ borderTop: '1px solid #F1F5F9', pt: 1.5, cursor: 'pointer' }} onClick={onOpenSynthesia}>
              {state.loading ? <Skeleton height={40} /> : state.error ? (
                <Typography color="text.secondary" sx={{ fontSize: 12 }}>Synthesia: {state.error}</Typography>
              ) : allowance ? (
                <>
                  <MeterRow
                    label={`Synthesia credits${s.credits_used_is_estimate ? ' (est.)' : ''}`}
                    value={used || 0}
                    total={allowance}
                    color={used / allowance > 0.85 ? C.red : C.violet}
                    right={`${fmt(used)} / ${fmt(allowance)}`}
                  />
                  <Typography color="text.secondary" sx={{ fontSize: 12, mt: -0.75 }}>
                    {fmt(s.published_videos)} videos published
                    {s.billing_cycle_renews_on ? ` · renews ${shortDate(s.billing_cycle_renews_on)}` : ''}
                  </Typography>
                </>
              ) : (
                <Typography color="text.secondary" sx={{ fontSize: 12 }}>
                  Synthesia: {fmt(s?.total_videos)} videos · {fmt(s?.total_credits_used)} credits used
                </Typography>
              )}
            </Box>
          )}
        </>
      )}
    </SectionCard>
  );
}

function IntegrationHealthCard({ integrations, loading, onNavigate }) {
  return (
    <SectionCard title="Integrations" subtitle="Connection health (last test)">
      {loading ? <Skeleton variant="rectangular" height={220} sx={{ borderRadius: 2 }} /> : (
        (integrations || []).map((it, i, arr) => {
          const st = !it.configured || it.active === false ? 'idle' : it.last_test_status || 'pending';
          const text = !it.configured
            ? 'Not configured'
            : it.active === false
              ? 'Disabled'
              : it.last_test_status === 'failed'
                ? `Failing · ${timeAgo(it.last_tested_at)}`
                : it.last_tested_at
                  ? `Healthy · tested ${timeAgo(it.last_tested_at)}`
                  : 'Not tested yet';
          return (
            <ListRow key={it.key} onClick={() => onNavigate(INTEGRATION_LINKS[it.key])} last={i === arr.length - 1}>
              <StatusDot status={st} />
              <Typography sx={{ fontSize: 13, fontWeight: 600, flex: 1 }}>
                {it.name}
                {it.domains > 1 && <Typography component="span" color="text.secondary" sx={{ fontSize: 12, ml: 0.5 }}>({it.domains} domains)</Typography>}
              </Typography>
              <Typography sx={{ fontSize: 12, color: st === 'failed' ? C.red : 'text.secondary' }}>{text}</Typography>
            </ListRow>
          );
        })
      )}
    </SectionCard>
  );
}

function TicketListCard({ title, subtitle, tickets, loading, onOpen, showRaisedBy = true }) {
  const list = tickets?.recent || [];
  return (
    <SectionCard title={title} subtitle={subtitle} action="Tickets" onAction={onOpen}>
      {loading ? <Skeleton variant="rectangular" height={220} sx={{ borderRadius: 2 }} /> : list.length === 0 ? (
        <EmptyState icon={<TaskAltIcon />} text="No active tickets — all clear." />
      ) : list.map((t, i) => {
        const p = PRIORITY_META[t.priority] || PRIORITY_META.low;
        const s = TICKET_STATUS_META[t.status] || TICKET_STATUS_META.open;
        return (
          <ListRow key={t.id} onClick={onOpen} last={i === list.length - 1}>
            <Box sx={{ width: 4, alignSelf: 'stretch', borderRadius: 2, bgcolor: p.color, flexShrink: 0 }} />
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography sx={{ fontSize: 13, fontWeight: 600 }} noWrap>{t.title}</Typography>
              <Typography color="text.secondary" sx={{ fontSize: 12 }} noWrap>
                {t.ticket_id}
                {showRaisedBy && t.raised_by ? ` · ${t.raised_by}` : ''}
                {' · '}{t.assigned_to ? `→ ${t.assigned_to}` : 'Unassigned'}
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'right', flexShrink: 0 }}>
              <Typography sx={{ fontSize: 11.5, fontWeight: 700, color: s.color }}>{s.label}</Typography>
              <Typography color="text.secondary" sx={{ fontSize: 11.5 }}>{timeAgo(t.created_at)}</Typography>
            </Box>
          </ListRow>
        );
      })}
    </SectionCard>
  );
}

function AllocationsCard({ inventory, loading, onOpen, onOpenAsset }) {
  const list = inventory?.recent_allocations || [];
  return (
    <SectionCard title="Recent allocations" subtitle="Latest asset hand-outs and recoveries" action="Allocation" onAction={onOpen}>
      {loading ? <Skeleton variant="rectangular" height={220} sx={{ borderRadius: 2 }} /> : list.length === 0 ? (
        <EmptyState icon={<SwapHorizIcon />} text="No allocations yet." />
      ) : list.map((a, i) => (
        <ListRow key={a.id} onClick={() => onOpenAsset(a.asset_pk)} last={i === list.length - 1}>
          <Avatar sx={{ width: 32, height: 32, fontSize: 12, fontWeight: 700, bgcolor: a.status === 'active' ? '#EEF2FF' : '#F1F5F9', color: a.status === 'active' ? C.primary : '#64748B' }}>
            {initials(a.employee)}
          </Avatar>
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography sx={{ fontSize: 13, fontWeight: 600 }} noWrap>{a.employee}</Typography>
            <Typography color="text.secondary" sx={{ fontSize: 12 }} noWrap>{a.asset_type} · {a.asset_id}</Typography>
          </Box>
          <Box sx={{ textAlign: 'right', flexShrink: 0 }}>
            <Typography sx={{ fontSize: 11.5, fontWeight: 700, color: a.status === 'active' ? C.primary : '#64748B' }}>
              {a.status === 'active' ? 'Assigned' : 'Recovered'}
            </Typography>
            <Typography color="text.secondary" sx={{ fontSize: 11.5 }}>{shortDate(a.date)}</Typography>
          </Box>
        </ListRow>
      ))}
    </SectionCard>
  );
}

function JoinersCard({ people, loading, onOpen }) {
  const list = people?.upcoming_joiners || [];
  return (
    <SectionCard title="Upcoming joiners" subtitle="Starting in the next 30 days" action="Onboarding" onAction={onOpen}>
      {loading ? <Skeleton variant="rectangular" height={180} sx={{ borderRadius: 2 }} /> : list.length === 0 ? (
        <EmptyState icon={<PersonAddIcon />} text="No joiners scheduled in the next 30 days." />
      ) : list.map((j, i) => {
        const d = daysUntil(j.date_of_joining);
        return (
          <ListRow key={j.id} onClick={onOpen} last={i === list.length - 1}>
            <Avatar sx={{ width: 32, height: 32, fontSize: 12, fontWeight: 700, bgcolor: '#FEF3C7', color: '#92400E' }}>{initials(j.full_name)}</Avatar>
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography sx={{ fontSize: 13, fontWeight: 600 }} noWrap>{j.full_name}</Typography>
              <Typography color="text.secondary" sx={{ fontSize: 12 }} noWrap>{j.designation}</Typography>
            </Box>
            <Box sx={{ textAlign: 'right', flexShrink: 0 }}>
              <Typography sx={{ fontSize: 12, fontWeight: 700 }}>{d === 0 ? 'Today' : d === 1 ? 'Tomorrow' : `in ${d}d`}</Typography>
              <Chip
                size="small"
                icon={j.status === 'confirmed' ? <CheckCircleIcon /> : <HourglassTopIcon />}
                label={j.status === 'confirmed' ? 'Confirmed' : 'Pending'}
                sx={{ height: 20, fontSize: 11, '& .MuiChip-icon': { fontSize: 13 }, bgcolor: j.status === 'confirmed' ? '#D1FAE5' : '#FEF3C7', color: j.status === 'confirmed' ? '#065F46' : '#92400E' }}
              />
            </Box>
          </ListRow>
        );
      })}
    </SectionCard>
  );
}

function ActivityCard({ activity, loading, onOpen }) {
  const list = activity || [];
  return (
    <SectionCard title="Recent changes" subtitle="Latest write actions across the portal" action="Activity log" onAction={onOpen}>
      {loading ? <Skeleton variant="rectangular" height={180} sx={{ borderRadius: 2 }} /> : list.length === 0 ? (
        <EmptyState text="No recent activity." />
      ) : list.map((a, i) => {
        const failed = a.status_code >= 400;
        const color = failed ? C.red : a.method === 'DELETE' ? C.orange : a.method === 'POST' ? C.primary : C.sky;
        return (
          <ListRow key={a.id} last={i === list.length - 1}>
            <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: color, flexShrink: 0 }} />
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography sx={{ fontSize: 13 }} noWrap>{a.action}</Typography>
              <Typography color="text.secondary" sx={{ fontSize: 12 }} noWrap>{a.user}{failed ? ` · failed (${a.status_code})` : ''}</Typography>
            </Box>
            <Typography color="text.secondary" sx={{ fontSize: 11.5, flexShrink: 0 }}>{timeAgo(a.created_at)}</Typography>
          </ListRow>
        );
      })}
    </SectionCard>
  );
}

// ---------- page ----------

function Dashboard() {
  const { user, hasRole } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const isIT = hasRole('super_admin', 'it_specialist');
  const isPeople = hasRole('super_admin', 'hr', 'it_specialist');
  const isEmployee = hasRole('employee');
  const isSuperAdmin = hasRole('super_admin');

  const userName = user?.full_name || user?.email || 'there';
  const firstName = userName.split(' ')[0];
  const roleName = (user?.role || '').replace(/_/g, ' ');
  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    api.get('/dashboard/overview/')
      .then((res) => !cancelled && setData(res.data))
      .catch(() => !cancelled && setError('Failed to load dashboard data.'))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [reloadKey]);

  const tickets = data?.tickets;
  const people = data?.people;
  const inventory = data?.inventory;
  const integrations = data?.integrations;

  const live = useMemo(() => {
    const ok = (key) => {
      const it = (integrations || []).find((i) => i.key === key);
      return Boolean(it?.configured && it.active !== false);
    };
    return { suremdm: ok('suremdm'), teamviewer: ok('teamviewer'), synthesia: ok('synthesia') };
  }, [integrations]);

  const go = (path) => () => navigate(path);
  const openAsset = (id) => navigate(`/inventory/assets/${id}`);

  const inService = inventory ? inventory.total - (inventory.status_counts.retired || 0) : 0;
  const utilisation = inService > 0 ? Math.round((inventory.status_counts.assigned / inService) * 100) : 0;
  const criticalHigh = (tickets?.priority_counts?.critical || 0) + (tickets?.priority_counts?.high || 0);

  const quickActions = [
    { label: 'Raise ticket', icon: <AddIcon />, path: '/tickets', show: true },
    { label: 'Assign asset', icon: <SwapHorizIcon />, path: '/allocation', show: isIT },
    { label: 'New joiner', icon: <PersonAddIcon />, path: '/onboarding', show: isPeople },
    { label: 'Add asset', icon: <DevicesIcon />, path: '/inventory/assets', show: isIT },
  ].filter((a) => a.show);

  const kpis = [];
  if (isPeople) {
    kpis.push({
      label: 'Employees',
      value: fmt(people?.employee_status?.active),
      sub: `${fmt(people?.employees_total)} total · ${fmt(people?.employee_status?.on_leave)} on leave`,
      icon: <PeopleIcon />, color: C.primary, path: '/employees',
    });
  }
  kpis.push({
    label: isEmployee ? 'My open tickets' : 'Active tickets',
    value: fmt(tickets?.active),
    sub: isEmployee
      ? `${fmt(tickets?.status_counts?.resolved)} resolved so far`
      : `${criticalHigh} high/critical · ${fmt(tickets?.unassigned)} unassigned`,
    icon: <ConfirmationNumberIcon />, color: C.red, path: '/tickets',
  });
  if (isEmployee) {
    kpis.push(
      { label: 'In progress', value: fmt(tickets?.status_counts?.in_progress), sub: 'Being worked on by IT', icon: <HourglassTopIcon />, color: C.amber, path: '/tickets' },
      { label: 'Resolved', value: fmt((tickets?.status_counts?.resolved || 0) + (tickets?.status_counts?.closed || 0)), sub: 'Resolved or closed', icon: <TaskAltIcon />, color: C.green, path: '/tickets' },
    );
  }
  if (isIT) {
    kpis.push(
      {
        label: 'IT assets',
        value: fmt(inventory?.total),
        sub: `${fmt(inventory?.status_counts?.available)} in stock · ${fmt(inventory?.status_counts?.maintenance)} in repair`,
        icon: <DevicesIcon />, color: C.green, path: '/inventory/assets',
      },
      {
        label: 'Utilisation',
        value: `${utilisation}%`,
        sub: `${fmt(inventory?.status_counts?.assigned)} of ${fmt(inService)} in-service assigned`,
        icon: <DonutLargeIcon />, color: C.sky, path: '/inventory',
      },
      {
        label: 'Licence seats',
        value: fmt(inventory?.licenses?.available_seats),
        sub: `free of ${fmt(inventory?.licenses?.total_seats)} · ${fmt(inventory?.licenses?.total)} licences`,
        icon: <KeyIcon />, color: C.violet, path: '/inventory',
      },
    );
  }
  if (isPeople) {
    kpis.push({
      label: 'Pending onboardings',
      value: fmt(people?.pending_onboardings),
      sub: `${fmt(people?.upcoming_joiners?.length)} joining in 30 days`,
      icon: <PersonAddIcon />, color: C.amber, path: '/onboarding',
    });
  }
  const queueCount = 2 + (isIT ? 1 : 0) + (isSuperAdmin ? 1 : 0);
  const queueSize = queueCount === 3 ? { xs: 12, md: 6, lg: 4 } : { xs: 12, md: 6 };
  const kpiSize = kpis.length >= 6 ? { xs: 12, sm: 6, md: 4, xl: 2 } : kpis.length === 4 ? { xs: 12, sm: 6, lg: 3 } : { xs: 12, sm: 6, md: 4 };

  return (
    <Box sx={{ maxWidth: 1600, mx: 'auto' }}>
      {/* Header */}
      <Box
        sx={{
          mb: 2.5,
          px: { xs: 2.5, md: 3 },
          py: 2.5,
          borderRadius: '16px',
          background: 'linear-gradient(120deg, #0F172A 0%, #1E1B4B 55%, #312E81 100%)',
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 2,
        }}
      >
        <Box sx={{ position: 'absolute', top: -60, right: -20, width: 220, height: 220, borderRadius: '50%', background: 'rgba(99,102,241,0.18)', pointerEvents: 'none' }} />
        <Box sx={{ position: 'relative', flex: '1 1 280px' }}>
          <Typography sx={{ color: '#A5B4FC', fontSize: 12.5, fontWeight: 600, mb: 0.5 }}>{today}</Typography>
          <Typography sx={{ color: '#F8FAFC', fontWeight: 800, fontSize: { xs: 20, md: 24 }, lineHeight: 1.2 }}>
            {greeting()}, {firstName}
          </Typography>
          <Typography sx={{ color: '#94A3B8', fontSize: 13.5, mt: 0.5 }}>
            <span style={{ textTransform: 'capitalize' }}>{roleName}</span>
            {!loading && tickets && (
              <> · {tickets.active ? `${tickets.active} active ticket${tickets.active === 1 ? '' : 's'}` : 'no active tickets'}
                {isPeople && people?.pending_onboardings ? ` · ${people.pending_onboardings} onboarding${people.pending_onboardings === 1 ? '' : 's'} awaiting review` : ''}
              </>
            )}
          </Typography>
        </Box>
        <Box sx={{ position: 'relative', display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
          {quickActions.map((a) => (
            <Button
              key={a.label}
              size="small"
              startIcon={a.icon}
              onClick={go(a.path)}
              sx={{ color: '#E0E7FF', bgcolor: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)', '&:hover': { bgcolor: 'rgba(255,255,255,0.16)' } }}
            >
              {a.label}
            </Button>
          ))}
          <Tooltip title="Refresh">
            <IconButton size="small" onClick={() => setReloadKey((k) => k + 1)} sx={{ color: '#C7D2FE', border: '1px solid rgba(255,255,255,0.12)' }}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {error && <Alert severity="warning" sx={{ mb: 2.5 }} action={<Button size="small" onClick={() => setReloadKey((k) => k + 1)}>Retry</Button>}>{error}</Alert>}

      {/* KPI row */}
      <Grid container spacing={2} sx={{ mb: 2.5 }}>
        {kpis.map((k) => (
          <Grid key={k.label} size={kpiSize}>
            <KpiTile {...k} loading={loading} onClick={go(k.path)} />
          </Grid>
        ))}
      </Grid>

      {/* Tickets */}
      <Grid container spacing={2.5} sx={{ mb: 2.5 }}>
        <Grid size={{ xs: 12, lg: isEmployee ? 7 : 8 }}>
          {isEmployee ? (
            <TicketListCard title="My active tickets" subtitle="Tickets you raised that are still open" tickets={tickets} loading={loading} onOpen={go('/tickets')} showRaisedBy={false} />
          ) : (
            <TicketTrendCard tickets={tickets} loading={loading} onOpen={go('/tickets')} />
          )}
        </Grid>
        <Grid size={{ xs: 12, lg: isEmployee ? 5 : 4 }}>
          {isEmployee ? (
            <TicketTrendCard tickets={tickets} loading={loading} onOpen={go('/tickets')} />
          ) : (
            <TicketBreakdownCard tickets={tickets} loading={loading} onOpen={go('/tickets')} />
          )}
        </Grid>
      </Grid>

      {/* Inventory */}
      {isIT && (
        <Grid container spacing={2.5} sx={{ mb: 2.5 }}>
          <Grid size={{ xs: 12, lg: 7 }}>
            <InventoryByTypeCard inventory={inventory} loading={loading} onOpen={go('/inventory/assets')} />
          </Grid>
          <Grid size={{ xs: 12, lg: 5 }}>
            <AssetHealthCard inventory={inventory} loading={loading} onOpenAsset={openAsset} />
          </Grid>
        </Grid>
      )}

      {/* Endpoints & subscriptions */}
      {isIT && (
        <Grid container spacing={2.5} sx={{ mb: 2.5 }}>
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <MdmCard enabled={!loading && live.suremdm} onOpen={go('/integrations?tab=suremdm')} />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <RemoteAccessCard enabled={!loading && live.teamviewer} onOpen={go('/integrations?tab=teamviewer')} />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <LicensesCard
              inventory={inventory}
              loading={loading}
              synthesiaEnabled={!loading && live.synthesia}
              onOpenInventory={go('/inventory')}
              onOpenSynthesia={go('/integrations?tab=synthesia')}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <IntegrationHealthCard integrations={integrations} loading={loading} onNavigate={navigate} />
          </Grid>
        </Grid>
      )}

      {/* Work queues */}
      {!isEmployee && (
        <Grid container spacing={2.5}>
          <Grid size={queueSize}>
            <TicketListCard title="Needs attention" subtitle="Active tickets, highest priority first" tickets={tickets} loading={loading} onOpen={go('/tickets')} />
          </Grid>
          {isIT && (
            <Grid size={queueSize}>
              <AllocationsCard inventory={inventory} loading={loading} onOpen={go('/allocation')} onOpenAsset={openAsset} />
            </Grid>
          )}
          <Grid size={queueSize}>
            <JoinersCard people={people} loading={loading} onOpen={go('/onboarding')} />
          </Grid>
          {isSuperAdmin && (
            <Grid size={queueSize}>
              <ActivityCard activity={data?.activity} loading={loading} onOpen={go('/activity-log')} />
            </Grid>
          )}
        </Grid>
      )}
    </Box>
  );
}

export default Dashboard;
