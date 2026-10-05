<?php

namespace App\Services;

use App\Models\Contract;
use App\Models\Department;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;

class DashboardService
{
    /**
     * Return all dashboard summary data.
     * DepartmentScope is handled automatically by the Contract model's GlobalScope.
     */
    public function getSummary(): array
    {
        $today = Carbon::today();
        $in90  = $today->copy()->addDays(90);

        // ── Query 1: Active contracts expiring within 90 days (covers 30/60/90 in one shot)
        $expiringRaw = Contract::query()
            ->where('status', 'active')
            ->where('end_date', '>=', $today)
            ->where('end_date', '<=', $in90)
            ->pluck('end_date')
            ->map(fn ($d) => Carbon::parse($d));

        $expiring30 = $expiringRaw->filter(fn ($d) => $d->lte($today->copy()->addDays(30)))->count();
        $expiring60 = $expiringRaw->filter(fn ($d) => $d->lte($today->copy()->addDays(60)))->count();
        $expiring90 = $expiringRaw->count(); // already filtered to <= 90

        // ── Query 2: Active contracts total (not expired by end_date)
        $activeCount = Contract::query()
            ->where('status', 'active')
            ->where('end_date', '>=', $today)
            ->count();

        // ── Query 3: By status (raw DB values)
        //    Bug #2: 'expired' is computed via accessor, not written to DB.
        //    We compute accessor-expired separately and merge.
        $byStatusRaw = Contract::query()
            ->select('status', DB::raw('COUNT(*) as total'))
            ->whereNotNull('status')
            ->groupBy('status')
            ->pluck('total', 'status')
            ->toArray();

        // Contracts with status='active' but end_date already past → accessor returns 'expired'
        $accessorExpiredCount = Contract::query()
            ->where('status', 'active')
            ->where('end_date', '<', $today)
            ->count();

        if ($accessorExpiredCount > 0) {
            $byStatusRaw['active']   = max(0, ($byStatusRaw['active'] ?? 0) - $accessorExpiredCount);
            $byStatusRaw['expired']  = ($byStatusRaw['expired'] ?? 0) + $accessorExpiredCount;
        }

        // Remove zero entries for cleaner chart
        $byStatus = collect($byStatusRaw)->filter(fn ($v) => $v > 0)->toArray();

        // ── Query 4: By department
        $byDepartment = Department::query()
            ->leftJoin('contracts', function ($join) use ($today) {
                $join->on('departments.id', '=', 'contracts.department_id')
                     ->whereNull('contracts.deleted_at');
            })
            ->select('departments.name', DB::raw('COUNT(contracts.id) as total'))
            ->groupBy('departments.id', 'departments.name')
            ->orderByDesc('total')
            ->limit(10)
            ->pluck('total', 'name')
            ->toArray();

        return compact(
            'activeCount',
            'expiring30',
            'expiring60',
            'expiring90',
            'byStatus',
            'byDepartment'
        );
    }
}
