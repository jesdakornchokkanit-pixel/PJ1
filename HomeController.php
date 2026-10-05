<?php

namespace App\Http\Controllers;

use App\Services\DashboardService;
use Illuminate\Http\Request;

class HomeController extends Controller
{
    public function __construct()
    {
        $this->middleware('auth');
    }

    public function index(DashboardService $dashboard)
    {
        $data = $dashboard->getSummary();

        return view('home', $data);
    }
}
