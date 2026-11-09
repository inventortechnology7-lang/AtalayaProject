const {expo}=require('./app.json');
// Explicit LAN build switch; tokens still require a trusted, isolated network.
module.exports=()=>({
 ...expo,
 android:{...expo.android,usesCleartextTraffic:process.env.EXPO_PUBLIC_ALLOW_HTTP_LAN==='true'},
 ios:{...expo.ios,infoPlist:{NSLocalNetworkUsageDescription:'Conectar con Katana en la red local.',...(process.env.EXPO_PUBLIC_ALLOW_HTTP_LAN==='true'?{NSAppTransportSecurity:{NSAllowsArbitraryLoads:true}}:{})}}
});
