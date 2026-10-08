package com.rafiqai.app

import android.app.Activity
import com.android.billingclient.api.*
import com.rafiqai.app.data.network.ApiClientFactory
import com.rafiqai.app.data.network.PurchaseVerifyBody
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class BillingManager(private val app: RafiqApplication, private val scope: CoroutineScope) : PurchasesUpdatedListener {
    private val client = BillingClient.newBuilder(app).setListener(this).enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build()).build()
    fun connect(onReady: () -> Unit = {}) { client.startConnection(object: BillingClientStateListener { override fun onBillingServiceDisconnected() {}; override fun onBillingSetupFinished(result: BillingResult) { if (result.responseCode == BillingClient.BillingResponseCode.OK) { onReady(); queryOwned() } } }) }
    fun queryProducts(ids: List<String>, callback: (List<ProductDetails>) -> Unit) {
        client.queryProductDetailsAsync(QueryProductDetailsParams.newBuilder().setProductList(ids.map { QueryProductDetailsParams.Product.newBuilder().setProductId(it).setProductType(BillingClient.ProductType.SUBS).build() }).build()) { result, details -> if (result.responseCode == BillingClient.BillingResponseCode.OK) callback(details.productDetailsList) }
    }
    fun launch(activity: Activity, details: ProductDetails) {
        val offer = details.subscriptionOfferDetails?.firstOrNull() ?: return
        val params = BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(details).setOfferToken(offer.offerToken).build()
        client.launchBillingFlow(activity, BillingFlowParams.newBuilder().setProductDetailsParamsList(listOf(params)).build())
    }
    private fun queryOwned() { client.queryPurchasesAsync(QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.SUBS).build()) { result, purchases -> if (result.responseCode == BillingClient.BillingResponseCode.OK) purchases.filter { it.purchaseState == Purchase.PurchaseState.PURCHASED }.forEach { verify(it) } } }
    override fun onPurchasesUpdated(result: BillingResult, purchases: MutableList<Purchase>?) { if (result.responseCode == BillingClient.BillingResponseCode.OK) purchases.orEmpty().filter { it.purchaseState == Purchase.PurchaseState.PURCHASED }.forEach { verify(it) } }
    private fun verify(purchase: Purchase) { purchase.products.firstOrNull()?.let { product -> scope.launch(Dispatchers.IO) { runCatching { ApiClientFactory.create(app.session).verifyPurchase(PurchaseVerifyBody(product, purchase.purchaseToken)) } } } }
}
