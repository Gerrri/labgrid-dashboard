import type {
  Target,
  TargetsResponse,
  Command,
  CommandOutput,
  HealthResponse,
  ScheduledCommand,
  ScheduledCommandsResponse,
} from '../types';

/**
 * Mock scheduled commands configuration
 */
const mockScheduledCommands: ScheduledCommand[] = [
  { name: 'Uptime', command: 'uptime -p', interval_seconds: 60, description: 'System uptime' },
  { name: 'Load', command: 'cat /proc/loadavg | cut -d\' \' -f1-3', interval_seconds: 30, description: 'System load average' },
  { name: 'Memory', command: 'free -h | grep Mem | awk \'{print $3"/"$2}\'', interval_seconds: 60, description: 'Memory usage' },
];

/**
 * Mock data for testing without backend
 */
const mockTargets: Target[] = [
  {
    name: 'rpi4-test-01',
    status: 'available',
    acquired_by: null,
    ip_address: '192.168.1.101',
    web_url: 'http://192.168.1.101:8080',
    resources: [
      {
        type: 'NetworkSerialPort',
        params: { host: '192.168.1.101', port: 4001 },
      },
      {
        type: 'EthernetPort',
        params: { switch: 'main-switch', interface: 'eth0' },
      },
    ],
    last_command_outputs: [
      {
        command: 'cat /etc/os-release',
        output: 'PRETTY_NAME="Raspbian GNU/Linux 11 (bullseye)"\nNAME="Raspbian GNU/Linux"\nVERSION_ID="11"\nVERSION="11 (bullseye)"',
        timestamp: new Date(Date.now() - 60000).toISOString(),
        exit_code: 0,
      },
    ],
    scheduled_outputs: {
      'Uptime': { command_name: 'Uptime', output: 'up 3 days, 2 hours', timestamp: new Date().toISOString(), exit_code: 0 },
      'Load': { command_name: 'Load', output: '0.15 0.10 0.05', timestamp: new Date().toISOString(), exit_code: 0 },
      'Memory': { command_name: 'Memory', output: '256Mi/1.0Gi', timestamp: new Date().toISOString(), exit_code: 0 },
    },
  },
  {
    name: 'imx8-board-02',
    status: 'acquired',
    acquired_by: 'john.doe',
    ip_address: '192.168.1.102',
    web_url: null,
    resources: [
      {
        type: 'USBSerialPort',
        params: { path: '/dev/ttyUSB0', baudrate: 115200 },
      },
    ],
    last_command_outputs: [
      {
        command: 'uname -a',
        output: 'Linux imx8-board 5.15.0-imx8 #1 SMP PREEMPT Thu Oct 12 12:34:56 UTC 2023 aarch64 GNU/Linux',
        timestamp: new Date(Date.now() - 120000).toISOString(),
        exit_code: 0,
      },
    ],
    scheduled_outputs: {
      'Uptime': { command_name: 'Uptime', output: 'up 12 hours', timestamp: new Date().toISOString(), exit_code: 0 },
      'Load': { command_name: 'Load', output: '0.82 0.65 0.50', timestamp: new Date().toISOString(), exit_code: 0 },
      'Memory': { command_name: 'Memory', output: '1.8Gi/4.0Gi', timestamp: new Date().toISOString(), exit_code: 0 },
    },
  },
  {
    name: 'stm32-dev-03',
    status: 'offline',
    acquired_by: null,
    ip_address: null,
    web_url: null,
    resources: [
      {
        type: 'USBSerialPort',
        params: { path: '/dev/ttyACM0', baudrate: 115200 },
      },
    ],
    last_command_outputs: [],
    scheduled_outputs: {},
  },
  {
    name: 'jetson-nano-04',
    status: 'available',
    acquired_by: null,
    ip_address: '192.168.1.104',
    web_url: 'http://192.168.1.104:8888',
    resources: [
      {
        type: 'NetworkSerialPort',
        params: { host: '192.168.1.104', port: 4001 },
      },
      {
        type: 'PowerPort',
        params: { model: 'pdu-01', port: 4 },
      },
    ],
    last_command_outputs: [
      {
        command: 'nvidia-smi',
        output: 'NVIDIA-SMI 32.7.1   Driver Version: 32.7.1   CUDA Version: 10.2',
        timestamp: new Date(Date.now() - 300000).toISOString(),
        exit_code: 0,
      },
    ],
    scheduled_outputs: {
      'Uptime': { command_name: 'Uptime', output: 'up 1 week, 2 days', timestamp: new Date().toISOString(), exit_code: 0 },
      'Load': { command_name: 'Load', output: '0.45 0.38 0.30', timestamp: new Date().toISOString(), exit_code: 0 },
      'Memory': { command_name: 'Memory', output: '2.1Gi/4.0Gi', timestamp: new Date().toISOString(), exit_code: 0 },
    },
  },
  {
    name: 'beaglebone-05',
    status: 'acquired',
    acquired_by: 'jane.smith',
    ip_address: '192.168.1.105',
    web_url: null,
    resources: [
      {
        type: 'NetworkSerialPort',
        params: { host: '192.168.1.105', port: 4001 },
      },
    ],
    last_command_outputs: [
      {
        command: 'free -h',
        output: '              total        used        free      shared  buff/cache   available\nMem:          512Mi       128Mi       256Mi        16Mi       128Mi       368Mi\nSwap:         256Mi         0B       256Mi',
        timestamp: new Date(Date.now() - 180000).toISOString(),
        exit_code: 0,
      },
    ],
    scheduled_outputs: {
      'Uptime': { command_name: 'Uptime', output: 'up 5 hours', timestamp: new Date().toISOString(), exit_code: 0 },
      'Load': { command_name: 'Load', output: '0.25 0.20 0.15', timestamp: new Date().toISOString(), exit_code: 0 },
      'Memory': { command_name: 'Memory', output: '128Mi/512Mi', timestamp: new Date().toISOString(), exit_code: 0 },
    },
  },
];

const mockCommands: Command[] = [
  { name: 'Linux Version', command: 'cat /etc/os-release', description: 'Shows the Linux distribution' },
  { name: 'System Time', command: 'date', description: 'Current system time' },
  { name: 'Kernel Version', command: 'uname -a', description: 'Kernel and system info' },
  { name: 'Uptime', command: 'uptime', description: 'System uptime' },
  { name: 'Memory Usage', command: 'free -h', description: 'RAM usage' },
];

/**
 * Simulates network delay
 */
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Mock API that simulates backend responses
 */
export const mockApi = {
  getTargets: async (): Promise<{ data: TargetsResponse }> => {
    await delay(500);
    return {
      data: {
        targets: mockTargets,
        total: mockTargets.length,
      },
    };
  },

  getTarget: async (name: string): Promise<{ data: Target }> => {
    await delay(300);
    const target = mockTargets.find((t) => t.name === name);
    if (!target) {
      throw new Error(`Target ${name} not found`);
    }
    return { data: target };
  },

  getCommands: async (_name: string): Promise<{ data: Command[] }> => {
    await delay(200);
    return { data: mockCommands };
  },

  executeCommand: async (
    targetName: string,
    commandName: string
  ): Promise<{ data: CommandOutput }> => {
    await delay(1000);
    const command = mockCommands.find((c) => c.name === commandName);
    return {
      data: {
        command: command?.command || commandName,
        output: `Mock output for "${commandName}" on ${targetName}\nCommand executed successfully.`,
        timestamp: new Date().toISOString(),
        exit_code: 0,
      },
    };
  },

  getHealth: async (): Promise<{ data: HealthResponse }> => {
    await delay(100);
    return {
      data: {
        status: 'ok',
        coordinator_connected: true,
        mock_mode: true,
      },
    };
  },

  getScheduledCommands: async (): Promise<{ data: ScheduledCommandsResponse }> => {
    await delay(100);
    return {
      data: {
        commands: mockScheduledCommands,
      },
    };
  },
};

export default mockApi;
