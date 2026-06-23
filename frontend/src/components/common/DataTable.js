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
import SearchIcon from '@mui/icons-material/Search';

function DataTable({
  rows = [],
  columns = [],
  loading = false,
  onAdd,
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

        {/* Add button */}
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

      {/* Table with horizontal scroll on small screens */}
      <Box
        sx={{
          width: '100%',
          overflowX: 'auto',
          WebkitOverflowScrolling: 'touch',
          borderRadius: '10px',
          border: '1px solid #E2E8F0',
          bgcolor: '#FFFFFF',
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
          autoHeight
          sx={{
            border: 'none',
            minWidth: isMobile ? 500 : 'auto',
            fontSize: { xs: 12.5, sm: 13.5 },
            '& .MuiDataGrid-columnHeaders': {
              backgroundColor: '#F8FAFC',
              borderBottom: '1px solid #E2E8F0',
            },
            '& .MuiDataGrid-columnHeaderTitle': {
              fontWeight: 700,
              fontSize: 12,
              color: '#64748B',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            },
            '& .MuiDataGrid-row': {
              cursor: rest.onRowClick ? 'pointer' : 'default',
              '&:hover': { backgroundColor: '#F8FAFC' },
              '&:last-child .MuiDataGrid-cell': { borderBottom: 'none' },
            },
            '& .MuiDataGrid-cell': {
              borderBottom: '1px solid #F1F5F9',
              color: '#1E293B',
              '&:focus': { outline: 'none' },
              '&:focus-within': { outline: 'none' },
            },
            '& .MuiDataGrid-footerContainer': {
              borderTop: '1px solid #E2E8F0',
              backgroundColor: '#F8FAFC',
            },
            '& .MuiDataGrid-columnSeparator': { display: 'none' },
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
