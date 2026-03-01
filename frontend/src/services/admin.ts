import api from '@/services/api';

export interface SavingsResponse {
    totalQueries: number;
    tokensSaved: number;
    inrSaved: number;
    avgCostReductionPct: number;
    byDay: Array<{
        date: string;
        queries: number;
        tokensSaved: number;
        inrSaved: number;
    }>;
}

export async function getSavings(): Promise<SavingsResponse> {
    const res = await api.get('/admin/savings');
    return res.data as SavingsResponse;
}
