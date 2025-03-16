'use client';

import React, { useState, useRef, useEffect, KeyboardEvent, FocusEvent } from 'react';

export interface EditableCellProps {
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
  
  // Text alignment
  align?: 'left' | 'right' | 'center';
}

const EditableCell: React.FC<EditableCellProps> = ({
  value,
  isEditable,
  onEdit,
  validator,
  formatter,
  type = 'text',
  options = [],
  className = '',
  isCalculating = false,
  align = 'left',
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState<any>(value);
  const [isValid, setIsValid] = useState(true);
  const inputRef = useRef<HTMLInputElement | HTMLSelectElement>(null);
  
  // Update editValue when value prop changes (and not editing)
  useEffect(() => {
    if (!isEditing) {
      setEditValue(value);
    }
  }, [value, isEditing]);
  
  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      // Use requestAnimationFrame to ensure the DOM is ready
      requestAnimationFrame(() => {
        try {
          if (inputRef.current) {
            inputRef.current.focus();
            
            // For text inputs, select all text for easy replacement
            if (type === 'text' || type === 'number') {
              (inputRef.current as HTMLInputElement).select?.();
            }
          }
        } catch (error) {
          console.error('Error focusing input in EditableCell:', error);
        }
      });
    }
    
    // Cleanup function to handle component unmounting during edit
    return () => {
      // If component unmounts while editing, ensure we don't leave any pending state
      if (isEditing) {
        setIsEditing(false);
      }
    };
  }, [isEditing, type]);
  
  const handleClick = () => {
    if (isEditable && !isCalculating && !isEditing) {
      setIsEditing(true);
    }
  };
  
  const validateInput = (val: any): boolean => {
    if (validator) {
      return validator(val);
    }
    
    // Default validation based on type
    if (type === 'number') {
      return !isNaN(Number(val));
    }
    
    return true;
  };
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const newValue = type === 'number' ? 
      (e.target.value === '' ? '' : Number(e.target.value)) : 
      e.target.value;
    
    setEditValue(newValue);
    setIsValid(validateInput(newValue));
  };
  
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement | HTMLSelectElement>) => {
    try {
      if (e.key === 'Enter') {
        commitEdit();
      } else if (e.key === 'Escape') {
        cancelEdit();
      }
    } catch (error) {
      console.error('Error in EditableCell handleKeyDown:', error);
      // Reset to original value if there's an error
      cancelEdit();
    }
  };
  
  const handleBlur = (e: FocusEvent<HTMLInputElement | HTMLSelectElement>) => {
    try {
      // Prevent immediate blur when selecting from dropdown
      if (type === 'select' && e.relatedTarget && e.relatedTarget.tagName === 'OPTION') {
        return;
      }
      
      commitEdit();
    } catch (error) {
      console.error('Error in EditableCell handleBlur:', error);
      // Reset to original value if there's an error
      cancelEdit();
    }
  };
  
  const commitEdit = () => {
    try {
      if (isValid && editValue !== value) {
        // Use requestAnimationFrame to ensure UI remains responsive
        requestAnimationFrame(() => {
          try {
            onEdit(editValue);
          } catch (error) {
            console.error('Error in EditableCell onEdit callback:', error);
          }
        });
      }
      setIsEditing(false);
    } catch (error) {
      console.error('Error in EditableCell commitEdit:', error);
      cancelEdit();
    }
  };
  
  const cancelEdit = () => {
    setEditValue(value);
    setIsEditing(false);
  };
  
  const displayValue = formatter ? formatter(value) : value?.toString() || '';
  
  // Determine text alignment class
  const alignClass = align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left';
  
  // Base cell styles
  const cellClasses = `py-2 px-3 ${alignClass} ${className} ${
    isEditable && !isCalculating ? 'cursor-pointer hover:bg-gray-50' : ''
  } ${isCalculating ? 'opacity-50' : ''}`;
  
  // Render input based on type
  const renderEditInput = () => {
    const commonProps = {
      ref: inputRef as any,
      onBlur: handleBlur,
      onKeyDown: handleKeyDown,
      className: `w-full px-2 py-1 border ${isValid ? 'border-gray-300' : 'border-red-500'} rounded`,
    };
    
    switch (type) {
      case 'number':
        return (
          <input
            type="number"
            value={editValue}
            onChange={handleChange}
            step="any"
            {...commonProps}
          />
        );
      
      case 'select':
        return (
          <select
            value={editValue}
            onChange={handleChange}
            {...commonProps}
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );
      
      case 'date':
        return (
          <input
            type="date"
            value={editValue}
            onChange={handleChange}
            {...commonProps}
          />
        );
      
      default: // text
        return (
          <input
            type="text"
            value={editValue}
            onChange={handleChange}
            {...commonProps}
          />
        );
    }
  };
  
  return (
    <div 
      className={`${cellClasses} ${isEditing ? 'p-0' : ''} ${isEditable ? 'editable-cell' : ''}`}
      onClick={handleClick}
      data-is-editable={isEditable}
    >
      {isEditing ? (
        renderEditInput()
      ) : (
        <div className={`${isEditable ? 'editable-cell-content' : ''}`}>
          {displayValue}
        </div>
      )}
    </div>
  );
};

export default EditableCell;
