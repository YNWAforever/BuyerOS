import 'server-only';
import {marketingHandlers} from './boundary';

export const marketingIntakeHandlers = marketingHandlers(() => process.env);
