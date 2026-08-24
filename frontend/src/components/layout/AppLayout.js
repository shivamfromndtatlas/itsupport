import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  IconButton,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
  Tooltip,
  Collapse,
  Menu,
  MenuItem,
  useMediaQuery,
  useTheme,
  SwipeableDrawer,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import DashboardIcon from '@mui/icons-material/Dashboard';
import PeopleIcon from '@mui/icons-material/People';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import BadgeIcon from '@mui/icons-material/Badge';
import DevicesIcon from '@mui/icons-material/Devices';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import LogoutIcon from '@mui/icons-material/Logout';
import InventoryIcon from '@mui/icons-material/Inventory';
import HistoryIcon from '@mui/icons-material/History';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import TuneIcon from '@mui/icons-material/Tune';
import CloudSyncIcon from '@mui/icons-material/CloudSync';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { useAuth } from '../../context/AuthContext';

const DRAWER_OPEN_WIDTH = 256;
const DRAWER_COLLAPSED_WIDTH = 68;

const SB = {
  bg: '#0F172A',
  hover: '#1E293B',
  activeBg: 'rgba(79,70,229,0.15)',
  activeBorder: '#4F46E5',
  text: '#94A3B8',
  textActive: '#FFFFFF',
  section: '#475569',
  divider: 'rgba(255,255,255,0.06)',
};

const NAV_SECTIONS = [
  {
    title: '',
    items: [
      { label: 'Dashboard', icon: <DashboardIcon sx={{ fontSize: 20 }} />, path: '/dashboard', roles: ['super_admin', 'hr', 'it_specialist', 'employee'] },
    ],
  },
  {
    title: 'HR',
    roles: ['super_admin', 'hr', 'it_specialist'],
    items: [
      { label: 'Employees', icon: <PeopleIcon sx={{ fontSize: 20 }} />, path: '/employees', roles: ['super_admin', 'hr', 'it_specialist'] },
      { label: 'New Joiner Onboarding', icon: <PersonAddIcon sx={{ fontSize: 20 }} />, path: '/onboarding', roles: ['super_admin', 'hr', 'it_specialist'] },
      { label: 'Alias Name Checker', icon: <BadgeIcon sx={{ fontSize: 20 }} />, path: '/alias-checker', roles: ['super_admin', 'hr', 'it_specialist'] },
    ],
  },
  {
    title: 'IT Operations',
    roles: ['super_admin', 'it_specialist'],
    items: [
      { label: 'IT Assets', icon: <DevicesIcon sx={{ fontSize: 20 }} />, path: '/inventory/assets', roles: ['super_admin', 'it_specialist'] },
      { label: 'Inventory Dashboard', icon: <InventoryIcon sx={{ fontSize: 20 }} />, path: '/inventory', roles: ['super_admin', 'it_specialist'] },
      { label: 'Asset Allocation', icon: <SwapHorizIcon sx={{ fontSize: 20 }} />, path: '/allocation', roles: ['super_admin', 'it_specialist'] },
      { label: 'SOP Management', icon: <MenuBookIcon sx={{ fontSize: 20 }} />, path: '/sop', roles: ['super_admin', 'it_specialist'] },
      { label: 'Inventory Config', icon: <TuneIcon sx={{ fontSize: 20 }} />, path: '/inventory/config', roles: ['super_admin', 'it_specialist'] },
      { label: 'Sure MDM', icon: <CloudSyncIcon sx={{ fontSize: 20 }} />, path: '/integrations', roles: ['super_admin', 'it_specialist'] },
    ],
  },
  {
    title: 'Support',
    items: [
      { label: 'Tickets', icon: <ConfirmationNumberIcon sx={{ fontSize: 20 }} />, path: '/tickets', roles: ['super_admin', 'hr', 'it_specialist', 'employee'] },
    ],
  },
  {
    title: 'Admin',
    roles: ['super_admin'],
    items: [
      { label: 'User Management', icon: <AdminPanelSettingsIcon sx={{ fontSize: 20 }} />, path: '/users', roles: ['super_admin'] },
      { label: 'Organisations', icon: <PeopleIcon sx={{ fontSize: 20 }} />, path: '/organisations', roles: ['super_admin'] },
      { label: 'Activity Log', icon: <HistoryIcon sx={{ fontSize: 20 }} />, path: '/activity-log', roles: ['super_admin'] },
    ],
  },
];

function NavSection({ section, open, currentPath, onNavigate, userRole, onNavItemClick }) {
  const [expanded, setExpanded] = useState(true);

  const visibleItems = section.items.filter(
    (item) => !item.roles || item.roles.includes(userRole)
  );
  if (visibleItems.length === 0) return null;
  if (section.roles && !section.roles.includes(userRole)) return null;

  return (
    <Box sx={{ mb: 0.5 }}>
      {section.title && open && (
        <Box
          onClick={() => setExpanded(!expanded)}
          sx={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            px: 2, py: 0.75, cursor: 'pointer', '&:hover': { opacity: 0.8 },
          }}
        >
          <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: SB.section, textTransform: 'uppercase' }}>
            {section.title}
          </Typography>
          {expanded
            ? <ExpandLess sx={{ fontSize: 14, color: SB.section }} />
            : <ExpandMore sx={{ fontSize: 14, color: SB.section }} />}
        </Box>
      )}

      <Collapse in={!section.title || !open || expanded} timeout="auto" unmountOnExit={false}>
        {visibleItems.map((item) => {
          const isActive = currentPath === item.path || currentPath.startsWith(item.path + '/');
          return (
            <ListItem key={item.path} disablePadding sx={{ px: 1.5, mb: 0.25 }}>
              <Tooltip title={!open ? item.label : ''} placement="right" arrow>
                <ListItemButton
                  onClick={() => { onNavigate(item.path); onNavItemClick?.(); }}
                  sx={{
                    minHeight: 40, borderRadius: '8px',
                    justifyContent: open ? 'initial' : 'center',
                    pl: open ? 1.5 : 1, pr: 1, position: 'relative',
                    backgroundColor: isActive ? SB.activeBg : 'transparent',
                    borderLeft: isActive ? `3px solid ${SB.activeBorder}` : '3px solid transparent',
                    '&:hover': { backgroundColor: isActive ? SB.activeBg : SB.hover },
                    transition: 'all 0.15s ease',
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 0, mr: open ? 1.5 : 'auto', justifyContent: 'center', color: isActive ? SB.activeBorder : SB.text }}>
                    {item.icon}
                  </ListItemIcon>
                  {open && (
                    <ListItemText
                      primary={item.label}
                      slotProps={{
                        primary: {
                          style: { fontSize: 13.5, fontWeight: isActive ? 600 : 400, color: isActive ? SB.textActive : SB.text, lineHeight: 1.4 },
                        },
                      }}
                    />
                  )}
                </ListItemButton>
              </Tooltip>
            </ListItem>
          );
        })}
      </Collapse>

      {section.title && (
        <Box sx={{ mx: 2, my: 1, borderBottom: `1px solid ${SB.divider}` }} />
      )}
    </Box>
  );
}

function SidebarContent({ open, currentPath, navigate, userRole, userName, initials, onNavItemClick, onLogout }) {
  const [anchorEl, setAnchorEl] = useState(null);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: SB.bg }}>
      {/* Logo */}
      <Box sx={{ display: 'flex', alignItems: 'center', height: 64, px: 2, flexShrink: 0, borderBottom: `1px solid ${SB.divider}` }}>
        <Box sx={{
          width: 34, height: 34, borderRadius: '10px',
          background: 'linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0, boxShadow: '0 4px 12px rgba(79,70,229,0.4)',
        }}>
          <Typography sx={{ color: '#fff', fontWeight: 800, fontSize: 15, letterSpacing: '-0.5px' }}>IT</Typography>
        </Box>
        {open && (
          <Box sx={{ ml: 1.5, overflow: 'hidden' }}>
            <Typography sx={{ color: '#F8FAFC', fontWeight: 700, fontSize: 14.5, lineHeight: 1.2, whiteSpace: 'nowrap' }}>IT Support</Typography>
            <Typography sx={{ color: SB.text, fontSize: 11, whiteSpace: 'nowrap' }}>Portal</Typography>
          </Box>
        )}
      </Box>

      {/* Nav */}
      <Box sx={{ flexGrow: 1, overflowY: 'auto', overflowX: 'hidden', py: 1.5 }}>
        <List disablePadding>
          {NAV_SECTIONS.map((section, idx) => (
            <NavSection
              key={idx}
              section={section}
              open={open}
              currentPath={currentPath}
              onNavigate={navigate}
              userRole={userRole}
              onNavItemClick={onNavItemClick}
            />
          ))}
        </List>
      </Box>

      {/* User footer */}
      <Box sx={{ p: 1.5, borderTop: `1px solid ${SB.divider}`, flexShrink: 0 }}>
        <Box
          onClick={(e) => setAnchorEl(e.currentTarget)}
          sx={{
            display: 'flex', alignItems: 'center', gap: 1.5, p: 1,
            borderRadius: '10px', cursor: 'pointer',
            '&:hover': { bgcolor: SB.hover }, transition: 'background 0.15s',
            justifyContent: open ? 'flex-start' : 'center',
          }}
        >
          <Avatar sx={{ width: 32, height: 32, fontSize: 12, fontWeight: 700, bgcolor: '#4F46E5', flexShrink: 0 }}>
            {initials}
          </Avatar>
          {open && (
            <>
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography sx={{ color: '#E2E8F0', fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {userName}
                </Typography>
                <Typography sx={{ color: SB.text, fontSize: 11, textTransform: 'capitalize' }}>
                  {(userRole || '').replace(/_/g, ' ')}
                </Typography>
              </Box>
              <KeyboardArrowDownIcon sx={{ color: SB.text, fontSize: 18, flexShrink: 0 }} />
            </>
          )}
        </Box>
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={() => setAnchorEl(null)}
          PaperProps={{
            sx: { mt: -1, ml: 1, minWidth: 180, boxShadow: '0 10px 40px rgba(0,0,0,0.15)', border: '1px solid #E2E8F0', borderRadius: '10px' },
          }}
          transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
        >
          <MenuItem onClick={() => { setAnchorEl(null); onLogout(); }} sx={{ color: 'error.main', gap: 1.5, fontSize: 14 }}>
            <LogoutIcon fontSize="small" />
            Sign Out
          </MenuItem>
        </Menu>
      </Box>
    </Box>
  );
}

function AppLayout() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const [desktopOpen, setDesktopOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const userRole = user?.role || 'employee';
  const userName = user?.full_name || user?.email || 'User';
  const initials = userName.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);

  const drawerWidth = desktopOpen ? DRAWER_OPEN_WIDTH : DRAWER_COLLAPSED_WIDTH;

  const pageLabel = (() => {
    const path = location.pathname;
    const all = NAV_SECTIONS.flatMap((s) => s.items);
    const found = all.find((i) => path === i.path || path.startsWith(i.path + '/'));
    return found?.label || 'IT Support Portal';
  })();

  const handleLogout = () => { logout(); navigate('/login'); };

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>

      {/* ── Desktop: permanent collapsible drawer ── */}
      {!isMobile && (
        <Drawer
          variant="permanent"
          sx={{
            width: drawerWidth,
            flexShrink: 0,
            whiteSpace: 'nowrap',
            '& .MuiDrawer-paper': {
              width: drawerWidth,
              overflowX: 'hidden',
              transition: 'width 0.25s cubic-bezier(0.4,0,0.2,1)',
              backgroundColor: SB.bg,
              borderRight: 'none',
            },
          }}
        >
          <SidebarContent
            open={desktopOpen}
            currentPath={location.pathname}
            navigate={navigate}
            userRole={userRole}
            userName={userName}
            initials={initials}
            onLogout={handleLogout}
          />
        </Drawer>
      )}

      {/* ── Mobile: swipeable temporary drawer ── */}
      {isMobile && (
        <SwipeableDrawer
          open={mobileOpen}
          onOpen={() => setMobileOpen(true)}
          onClose={() => setMobileOpen(false)}
          swipeAreaWidth={20}
          disableBackdropTransition={false}
          sx={{
            '& .MuiDrawer-paper': {
              width: DRAWER_OPEN_WIDTH,
              backgroundColor: SB.bg,
              borderRight: 'none',
            },
          }}
        >
          <SidebarContent
            open={true}
            currentPath={location.pathname}
            navigate={navigate}
            userRole={userRole}
            userName={userName}
            initials={initials}
            onNavItemClick={() => setMobileOpen(false)}
            onLogout={handleLogout}
          />
        </SwipeableDrawer>
      )}

      {/* ── Main content ── */}
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

        {/* Top bar */}
        <Box
          sx={{
            height: 64, display: 'flex', alignItems: 'center',
            px: { xs: 1.5, sm: 2.5 },
            bgcolor: 'background.paper',
            borderBottom: '1px solid', borderColor: 'divider',
            flexShrink: 0, position: 'sticky', top: 0, zIndex: 100, gap: 1.5,
          }}
        >
          {/* Hamburger for mobile; collapse toggle for desktop */}
          <IconButton
            onClick={() => isMobile ? setMobileOpen(true) : setDesktopOpen(!desktopOpen)}
            size="small"
            sx={{ color: 'text.secondary', '&:hover': { bgcolor: 'grey.100' } }}
          >
            {(!isMobile && desktopOpen) ? <ChevronLeftIcon /> : <MenuIcon />}
          </IconButton>

          <Typography
            variant="h6"
            fontWeight={700}
            color="text.primary"
            sx={{
              fontSize: { xs: 15, sm: 17 },
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {pageLabel}
          </Typography>

          <Box
            sx={{
              display: 'flex', alignItems: 'center', gap: 1,
              bgcolor: 'grey.50', border: '1px solid', borderColor: 'divider',
              borderRadius: '10px', px: { xs: 1, sm: 1.5 }, py: 0.75, flexShrink: 0,
            }}
          >
            <Avatar sx={{ width: 28, height: 28, fontSize: 11, bgcolor: 'primary.main' }}>
              {initials}
            </Avatar>
            <Box sx={{ display: { xs: 'none', sm: 'block' } }}>
              <Typography variant="body2" fontWeight={600} sx={{ fontSize: 13, lineHeight: 1.2 }}>
                {userName}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: 11, textTransform: 'capitalize' }}>
                {userRole.replace(/_/g, ' ')}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Page content */}
        <Box
          component="main"
          sx={{ flexGrow: 1, p: { xs: 1.5, sm: 2, md: 3 }, overflow: 'auto' }}
        >
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}

export default AppLayout;
