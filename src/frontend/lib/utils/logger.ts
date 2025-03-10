/**
 * Frontend logging utility
 * Provides logging functionality with file output for debugging
 */

import apiClient from '../api/apiClient';

// Log levels
export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARN = 'WARN',
  ERROR = 'ERROR'
}

// Log entry interface
interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  data?: any;
}

class Logger {
  private static instance: Logger;
  private logBuffer: LogEntry[] = [];
  private maxBufferSize: number = 1000;
  private isWritingToFile: boolean = false;
  private logPrefix: string = 'OPTION_CHAIN_DEBUG';

  private constructor() {
    // Clear log file on initialization
    this.clearLogFile();
    
    // Set up interval to flush logs
    setInterval(() => this.flushLogs(), 5000);
    
    // Flush logs on window unload
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => {
        this.flushLogs(true);
      });
    }
  }

  public static getInstance(): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger();
    }
    return Logger.instance;
  }

  private getTimestamp(): string {
    return new Date().toISOString();
  }

  private async clearLogFile(): Promise<void> {
    try {
      // Use apiClient to call a backend endpoint that clears the log file
      await apiClient.post('/debug/clear-logs', null, { type: 'frontend' });
      console.log('Frontend log file cleared');
    } catch (error) {
      console.error('Failed to clear frontend log file:', error);
    }
  }

  private async flushLogs(force: boolean = false): Promise<void> {
    // Don't flush if already writing or buffer is empty
    if (this.isWritingToFile || this.logBuffer.length === 0) {
      return;
    }

    // Only flush if buffer is large enough or force is true
    if (!force && this.logBuffer.length < 50) {
      return;
    }

    this.isWritingToFile = true;
    
    try {
      const logsToWrite = [...this.logBuffer];
      this.logBuffer = [];
      
      // Format logs for writing
      const formattedLogs = logsToWrite.map(entry => {
        const dataStr = entry.data ? ` | ${JSON.stringify(entry.data)}` : '';
        return `${entry.timestamp} [${entry.level}] ${entry.message}${dataStr}`;
      }).join('\n');
      
      // Send logs to backend using apiClient
      await apiClient.post('/debug/log', {
        logs: formattedLogs,
        type: 'frontend'
      });
    } catch (error) {
      console.error('Failed to write logs to file:', error);
      // Put logs back in buffer
      this.logBuffer = [...this.logBuffer, ...this.logBuffer];
      // Trim buffer if it's too large
      if (this.logBuffer.length > this.maxBufferSize) {
        this.logBuffer = this.logBuffer.slice(-this.maxBufferSize);
      }
    } finally {
      this.isWritingToFile = false;
    }
  }

  public log(level: LogLevel, message: string, data?: any): void {
    const entry: LogEntry = {
      timestamp: this.getTimestamp(),
      level,
      message: `${this.logPrefix}: ${message}`,
      data
    };
    
    // Add to buffer
    this.logBuffer.push(entry);
    
    // Also log to console
    const consoleMessage = `${entry.timestamp} [${entry.level}] ${entry.message}`;
    switch (level) {
      case LogLevel.DEBUG:
        console.debug(consoleMessage, data || '');
        break;
      case LogLevel.INFO:
        console.info(consoleMessage, data || '');
        break;
      case LogLevel.WARN:
        console.warn(consoleMessage, data || '');
        break;
      case LogLevel.ERROR:
        console.error(consoleMessage, data || '');
        break;
    }
    
    // Flush if buffer is getting large
    if (this.logBuffer.length >= 100) {
      this.flushLogs();
    }
  }

  public debug(message: string, data?: any): void {
    this.log(LogLevel.DEBUG, message, data);
  }

  public info(message: string, data?: any): void {
    this.log(LogLevel.INFO, message, data);
  }

  public warn(message: string, data?: any): void {
    this.log(LogLevel.WARN, message, data);
  }

  public error(message: string, data?: any): void {
    this.log(LogLevel.ERROR, message, data);
  }
}

// Export singleton instance
export const logger = Logger.getInstance();
export default logger;
