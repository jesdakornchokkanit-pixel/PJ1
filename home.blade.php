@extends('layouts.app')

@section('page-title', 'แดชบอร์ด')

@section('content')

{{-- ── Widget Cards ──────────────────────────────────────────── --}}
<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">

    {{-- Active Contracts --}}
    <div class="bg-white rounded-xl border border-slate-200 px-5 py-4">
        <p class="text-xs font-medium text-slate-500 mb-1">สัญญาที่ใช้งานอยู่</p>
        <p class="text-3xl font-bold text-slate-900">{{ number_format($activeCount) }}</p>
        <p class="text-xs text-slate-400 mt-1">ฉบับ</p>
    </div>

    {{-- Expiring 30 --}}
    <div class="bg-white rounded-xl border border-slate-200 px-5 py-4">
        <p class="text-xs font-medium text-slate-500 mb-1">หมดอายุใน 30 วัน</p>
        <p class="text-3xl font-bold {{ $expiring30 > 0 ? 'text-red-600' : 'text-slate-900' }}">
            {{ number_format($expiring30) }}
        </p>
        <p class="text-xs text-slate-400 mt-1">ฉบับ</p>
    </div>

    {{-- Expiring 60 --}}
    <div class="bg-white rounded-xl border border-slate-200 px-5 py-4">
        <p class="text-xs font-medium text-slate-500 mb-1">หมดอายุใน 60 วัน</p>
        <p class="text-3xl font-bold {{ $expiring60 > 0 ? 'text-amber-500' : 'text-slate-900' }}">
            {{ number_format($expiring60) }}
        </p>
        <p class="text-xs text-slate-400 mt-1">ฉบับ</p>
    </div>

    {{-- Expiring 90 --}}
    <div class="bg-white rounded-xl border border-slate-200 px-5 py-4">
        <p class="text-xs font-medium text-slate-500 mb-1">หมดอายุใน 90 วัน</p>
        <p class="text-3xl font-bold {{ $expiring90 > 0 ? 'text-yellow-500' : 'text-slate-900' }}">
            {{ number_format($expiring90) }}
        </p>
        <p class="text-xs text-slate-400 mt-1">ฉบับ</p>
    </div>

</div>

{{-- ── Charts ────────────────────────────────────────────────── --}}
<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">

    {{-- Contracts by Status --}}
    <div class="bg-white rounded-xl border border-slate-200 px-5 py-4">
        <p class="text-sm font-semibold text-slate-900 mb-4">สัญญาแยกตามสถานะ</p>
        @if(count($byStatus) > 0)
            <div class="flex justify-center">
                <canvas id="chartStatus" width="280" height="280"></canvas>
            </div>
        @else
            <p class="text-sm text-slate-400 text-center py-10">ไม่มีข้อมูล</p>
        @endif
    </div>

    {{-- Contracts by Department --}}
    <div class="bg-white rounded-xl border border-slate-200 px-5 py-4">
        <p class="text-sm font-semibold text-slate-900 mb-4">สัญญาแยกตามแผนก</p>
        @if(count($byDepartment) > 0)
            <canvas id="chartDepartment"></canvas>
        @else
            <p class="text-sm text-slate-400 text-center py-10">ไม่มีข้อมูล</p>
        @endif
    </div>

</div>

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<script>
(function () {
    'use strict';

    // ── Status Labels Map
    const STATUS_LABELS = {
        active:    'ใช้งาน',
        pending:   'รอดำเนินการ',
        renewed:   'ต่ออายุแล้ว',
        cancelled: 'ยกเลิก',
        expired:   'หมดอายุ',
    };

    const STATUS_COLORS = {
        active:    '#22c55e',
        pending:   '#f59e0b',
        renewed:   '#3b82f6',
        cancelled: '#6b7280',
        expired:   '#ef4444',
    };

    // ── Data from PHP
    const statusData    = @json($byStatus);
    const deptData      = @json($byDepartment);

    // ── Chart 1: Doughnut — by Status
    const statusCanvas = document.getElementById('chartStatus');
    if (statusCanvas && Object.keys(statusData).length > 0) {
        const statusKeys    = Object.keys(statusData);
        const statusValues  = Object.values(statusData);
        const statusLabels  = statusKeys.map(k => STATUS_LABELS[k] ?? k);
        const statusColors  = statusKeys.map(k => STATUS_COLORS[k] ?? '#94a3b8');

        new Chart(statusCanvas, {
            type: 'doughnut',
            data: {
                labels:   statusLabels,
                datasets: [{
                    data:            statusValues,
                    backgroundColor: statusColors,
                    borderWidth:     2,
                    borderColor:     '#fff',
                }],
            },
            options: {
                responsive:         false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { font: { size: 12 }, padding: 12 },
                    },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` ${ctx.label}: ${ctx.parsed} ฉบับ`,
                        },
                    },
                },
            },
        });
    }

    // ── Chart 2: Horizontal Bar — by Department
    const deptCanvas = document.getElementById('chartDepartment');
    if (deptCanvas && Object.keys(deptData).length > 0) {
        const deptLabels = Object.keys(deptData);
        const deptValues = Object.values(deptData);

        new Chart(deptCanvas, {
            type: 'bar',
            data: {
                labels:   deptLabels,
                datasets: [{
                    label:           'จำนวนสัญญา',
                    data:            deptValues,
                    backgroundColor: '#185FA5',
                    borderRadius:    4,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` ${ctx.parsed.x} ฉบับ`,
                        },
                    },
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { stepSize: 1, precision: 0 },
                        grid: { color: '#f1f5f9' },
                    },
                    y: {
                        ticks: { font: { size: 12 } },
                        grid: { display: false },
                    },
                },
            },
        });
    }
})();
</script>
@endpush
