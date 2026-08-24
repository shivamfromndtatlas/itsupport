import React, { useState, useMemo } from 'react';
import { DataGrid } from '@mui/x-data-grid';
import {
  Box,
  Button,
  TextField,
  Typography,
  InputAdornment,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RefreshIcon from '@mui/icons-material/Refresh';
import SearchIcon from '@mui/icons-material/Search';

function DataTable({
  rows = [],
  columns = [],
  loading = false,
  onAdd,
  onRefresh,
  refreshLabel = 'Refresh',
  addLabel = 'Add',
  title,
  searchable = false,
  toolbar,
  pageSize = 10,
  sx: dataGridSx,
  ...rest
}) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [searchText, setSearchText] = useState('');

  const filteredRows = useMemo(() => {
    if (!searchable || !searchText.trim()) return rows;
    const lower = searchText.toLowerCase();
    return rows.filter((row) =>
      Object.values(row).some((val) => String(val ?? '').toLowerCase().includes(lower))
    );
  }, [rows, searchText, searchable]);

  return (
    <Box>
      {/* Header — stacks on mobile */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          alignItems: { xs: 'stretch', sm: 'center' },
          justifyContent: 'space-between',
          mb: 2,
          gap: 1.5,
        }}
      >
        {/* Left side: title + toolbar + search */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            alignItems: { xs: 'stretch', sm: 'center' },
            gap: 1.5,
            flex: 1,
          }}
        >
          {title && (
            <Typography variant="h6" fontWeight={700} sx={{ fontSize: { xs: 15, sm: 16 } }}>
              {title}
            </Typography>
          )}
          {toolbar && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {toolbar}
            </Box>
          )}
          {searchable && (
            <TextField
              size="small"
              placeholder="Search..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" sx={{ color: 'text.disabled' }} />
                  </InputAdornment>
                ),
              }}
              sx={{
                width: { xs: '100%', sm: 220 },
                '& .MuiOutlinedInput-root': { height: 36, fontSize: 13 },
              }}
            />
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 1, alignSelf: { xs: 'stretch', sm: 'center' }, flexWrap: 'wrap' }}>
          {onRefresh && (
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={onRefresh}
              size="small"
              fullWidth={isMobile}
              sx={{ height: 36, px: 2, flexShrink: 0 }}
            >
              {refreshLabel}
            </Button>
          )}
          {onAdd && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={onAdd}
              size="small"
              fullWidth={isMobile}
              sx={{ height: 36, px: 2, flexShrink: 0 }}
            >
              {addLabel}
            </Button>
          )}
        </Box>
      </Box>

      {/* Table: the grid keeps horizontal scrolling inside itself so the
          page never scrolls sideways. Requires a width-constrained parent
          (flex children must set minWidth: 0). */}
      <Box
        sx={{
          width: '100%',
          minWidth: 0,
          maxWidth: '100%',
          borderRadius: '12px',
          border: '1px solid #E2E8F0',
          bgcolor: '#FFFFFF',
          overflow: 'hidden',
          boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
        }}
      >
        <DataGrid
          rows={filteredRows}
          columns={columns}
          loading={loading}
          initialState={{
            pagination: { paginationModel: { pageSize: isMobile ? 5 : pageSize } },
          }}
          pageSizeOptions={[5, 10, 25, 50]}
          disableRowSelectionOnClick
          disableColumnMenu
          autoHeight
          rowHeight={56}
          columnHeaderHeight={48}
          sx={{
            border: 'none',
            width: '100%',
            fontSize: { xs: 12.5, sm: 13.5 },
            // Keep the horizontal scrollbar attached to the grid body.
            '& .MuiDataGrid-virtualScroller': {
              overflowX: 'auto',
              WebkitOverflowScrolling: 'touch',
            },
            '& .MuiDataGrid-scrollbar': { height: 10 },
            '& .MuiDataGrid-columnHeaders': {
              backgroundColor: '#F8FAFC',
              borderBottom: '1px solid #E2E8F0',
            },
            '& .MuiDataGrid-columnHeader': {
              '&:focus, &:focus-within': { outline: 'none' },
            },
            '& .MuiDataGrid-columnHeaderTitle': {
              fontWeight: 700,
              fontSize: 11.5,
              color: '#64748B',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            },
            '& .MuiDataGrid-row': {
              cursor: rest.onRowClick ? 'pointer' : 'default',
              transition: 'background-color 0.15s ease',
              '&:nth-of-type(even)': { backgroundColor: '#FCFDFE' },
              '&:hover': { backgroundColor: '#EEF2FF' },
              '&:last-child .MuiDataGrid-cell': { borderBottom: 'none' },
            },
            '& .MuiDataGrid-cell': {
              borderBottom: '1px solid #F1F5F9',
              color: '#1E293B',
              display: 'flex',
              alignItems: 'center',
              '&:focus': { outline: 'none' },
              '&:focus-within': { outline: 'none' },
            },
            '& .MuiDataGrid-footerContainer': {
              borderTop: '1px solid #E2E8F0',
              backgroundColor: '#F8FAFC',
            },
            '& .MuiDataGrid-columnSeparator': {
              color: '#E2E8F0',
              '&:hover': { color: '#6366F1' },
            },
            '& .MuiDataGrid-columnSeparator--resizing': { color: '#6366F1' },
            '& .MuiTablePagination-root': { fontSize: 13, color: '#64748B' },
            ...dataGridSx,
          }}
          {...rest}
        />
      </Box>
    </Box>
  );
}

export default DataTable;
