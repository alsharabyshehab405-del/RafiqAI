package com.rafiqai.app
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.junit.Rule
import org.junit.Test
class OnboardingTest {
 @get:Rule val rule=createComposeRule()
 @Test fun onboardingShowsRafiq(){rule.setContent{Onboarding("ar") {}};rule.onNodeWithText("Rafiq AI").assertIsDisplayed();rule.onNodeWithText("ابدأ الآن").assertIsDisplayed()}
}
