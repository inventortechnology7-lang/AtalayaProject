import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',workers:1,use:{baseURL:'http://127.0.0.1:28081',headless:true,launchOptions:{executablePath:process.env.CHROMIUM_PATH||undefined}},reporter:'list'});
