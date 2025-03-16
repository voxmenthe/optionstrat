# Editable Positions Sheet Implementation Plan

## Overview
This plan outlines the implementation of an editable positions sheet where users can click on any non-calculated value to edit it, and clicking elsewhere or hitting return will trigger a recalculation of the position data.

## Current State
- Position data is displayed in a read-only table format
- Updates to positions require using a separate form
- Calculated values (Greeks, P&L) are derived from position parameters

## Implementation Goals
1. Make non-calculated fields directly editable in the positions table
2. Implement auto-recalculation after edits
3. Ensure proper validation of user inputs
4. Maintain performance during recalculations
5. Provide visual feedback during editing

## Technical Approach

### Phase 1: Editable Cell Component (2 days)

#### 1.1 Create EditableCell Component
```typescript
// Basic structure of the EditableCell component
interface EditableCellProps {
  value: any;
  isEditable: boolean;
  onEdit: (newValue: any) => void;
  validator?: (value: any) => boolean;
  formatter?: (value: any) => string;
  type?: 'text' | 'number' | 'select';
  options?: Array<{value: any, label: string}>; // For select type
}
```

#### 1.2 Implement Cell Editing Logic
- Double-click or single-click activation
- Focus management
- Keyboard navigation (tab, enter, escape)
- Input validation
- Blur handling

#### 1.3 Style Editable Cells
- Visual indicators for editable cells
- Focus and hover states
- Error state for invalid inputs

### Phase 2: Position Table Integration (2 days)

#### 2.1 Identify Editable Fields
- Quantity
- Strike price
- Expiration date
- Option type
- Entry price
- Exit price

#### 2.2 Update PositionsTable Component
- Replace static cells with EditableCell components
- Implement cell-specific validation rules
- Add handlers for edit events

#### 2.3 Position Update Logic
- Create updatePosition action in positionsStore
- Implement optimistic updates
- Handle API errors and rollbacks

### Phase 3: Recalculation System (3 days)

#### 3.1 Implement Trigger Mechanism
- Auto-recalculate on blur or enter key
- Debounce recalculations for performance
- Add manual recalculate button

#### 3.2 Calculation Service Updates
- Ensure calculation service can handle partial recalculations
- Optimize for performance with large position sets
- Implement caching for repeated calculations

#### 3.3 Visual Feedback
- Loading indicators during recalculation
- Highlight changed values
- Animation for updated cells

### Phase 4: Testing and Refinement (2 days)

#### 4.1 Unit Tests
- Test EditableCell component
- Test validation rules
- Test recalculation triggers

#### 4.2 Integration Tests
- Test position updates
- Test recalculation accuracy
- Test error handling

#### 4.3 Performance Testing
- Test with large position sets
- Measure and optimize recalculation time
- Ensure UI remains responsive

## Technical Specifications

### EditableCell Component API
```typescript
interface EditableCellProps {
  // Current value to display/edit
  value: any;
  
  // Whether this cell can be edited
  isEditable: boolean;
  
  // Callback when value is changed and confirmed
  onEdit: (newValue: any) => void;
  
  // Optional validation function
  validator?: (value: any) => boolean;
  
  // Optional formatting function for display
  formatter?: (value: any) => string;
  
  // Input type
  type?: 'text' | 'number' | 'select' | 'date';
  
  // Options for select type
  options?: Array<{value: any, label: string}>;
  
  // Custom styles
  className?: string;
  
  // Whether cell is currently being recalculated
  isCalculating?: boolean;
}
```

### Position Update Flow
1. User clicks on editable cell
2. Cell transforms into input field
3. User modifies value
4. On blur or enter:
   - Validate input
   - If valid, update local state
   - Trigger API update
   - Initiate recalculation
5. Show loading state during recalculation
6. Update calculated values when complete

### Data Model Updates
```typescript
interface EditablePositionField {
  fieldName: string;
  editable: boolean;
  type: 'text' | 'number' | 'select' | 'date';
  validator?: (value: any) => boolean;
  formatter?: (value: any) => string;
  options?: Array<{value: any, label: string}>;
}

// Configuration for which fields are editable and how
const EDITABLE_POSITION_FIELDS: Record<string, EditablePositionField> = {
  quantity: {
    fieldName: 'quantity',
    editable: true,
    type: 'number',
    validator: (value) => Number.isInteger(value) && value !== 0
  },
  strike: {
    fieldName: 'strike',
    editable: true,
    type: 'number',
    validator: (value) => value > 0
  },
  // Additional fields...
}
```

## Implementation Timeline

### Week 1
- Day 1-2: Develop EditableCell component
- Day 3-4: Integrate with PositionsTable
- Day 5: Begin recalculation system

### Week 2
- Day 1-2: Complete recalculation system
- Day 3: Testing and bug fixes
- Day 4-5: Performance optimization and refinement

## Future Enhancements
1. Batch editing of multiple positions
2. Undo/redo functionality
3. Conditional formatting based on position performance
4. Custom column visibility settings
5. Export/import of position data
